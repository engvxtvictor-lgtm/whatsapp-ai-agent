import re
import json
import httpx
import asyncio
import unicodedata
from sqlalchemy import select
from backend.system.config import settings
from backend.system.logger import logger
from backend.system.database import AsyncSession
from backend.system.models.web_models import ExamWeb
from backend.agent.services.schedule_service import get_available_slots_context
from backend.agent.services.prompts import SYSTEM_PROMPT, VIGILANTE_SYSTEM_PROMPT
from backend.agent.services.guardrails import (
    detect_jailbreak,
    validate_output_guardrail,
    extract_and_censor_cpf
)


# ──────────────────────────────────────────────
# CHAMADA À OPENAI (CHATGPT E WHISPER)
# ──────────────────────────────────────────────
async def transcribe_audio(audio_base64: str, mime_type: str) -> str:
    """Transcreve áudio base64 usando Whisper."""
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "sua_chave_openai_aqui":
        return ""
    import base64
    import tempfile
    import os
    
    ext = ".ogg"
    if "mp3" in mime_type: ext = ".mp3"
    elif "wav" in mime_type: ext = ".wav"
    
    audio_bytes = base64.b64decode(audio_base64)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_audio:
        temp_audio.write(audio_bytes)
        temp_audio_path = temp_audio.name
        
    try:
        url = f"{settings.OPENAI_API_URL}/audio/transcriptions"
        headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            with open(temp_audio_path, "rb") as f:
                # Force standard mime types to prevent OpenAI API from rejecting WhatsApp's specific mime string
                safe_mime = "audio/mpeg" if ext == ".mp3" else "audio/wav" if ext == ".wav" else "audio/ogg"
                files = {"file": (f"audio{ext}", f, safe_mime)}
                data = {"model": "whisper-1"}
                resp = await client.post(url, headers=headers, files=files, data=data)
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    logger.error(f"Erro HTTP Whisper: {exc.response.status_code} - {exc.response.text}")
                    return ""
                return resp.json().get("text", "")
    except Exception as e:
        logger.error(f"Erro Whisper: {e}")
        return ""
    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

async def _call_openai(system_prompt: str, messages: list, media: dict = None) -> str:
    """Chama a API da OpenAI. Retorna o texto da resposta."""
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "sua_chave_openai_aqui":
        raise Exception("OPENAI_API_KEY não configurada.")

    url = f"{settings.OPENAI_API_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    api_messages = [{"role": "system", "content": system_prompt}] + messages
    
    if media and media.get("type") == "image":
        for i in range(len(api_messages)-1, -1, -1):
            if api_messages[i]["role"] == "user":
                original_text = api_messages[i]["content"]
                api_messages[i]["content"] = [
                    {"type": "text", "text": original_text},
                    {"type": "image_url", "image_url": {"url": f"data:{media['mimetype']};base64,{media['data']}"}}
                ]
                break

    payload = {
        "model": settings.OPENAI_MODEL,
        "messages": api_messages,
        "temperature": 0.7,
        "max_tokens": 350,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _call_secondary_ai(system_prompt: str, messages: list) -> str:
    """Chama a API Secundária (Redundância). Usa endpoint compatível com OpenAI."""
    if not settings.SECONDARY_API_KEY or settings.SECONDARY_API_KEY == "sua_chave_gemini_ou_groq":
        raise Exception("SECONDARY_API_KEY não configurada.")

    # Se a chave começar com gsk_, é Groq. Se for AIza, é Gemini
    if settings.SECONDARY_API_KEY.startswith("gsk_"):
        url = "https://api.groq.com/openai/v1/chat/completions"
    elif settings.SECONDARY_API_KEY.startswith("AIza"):
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    else:
        url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {settings.SECONDARY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.SECONDARY_AI_MODEL,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": 0.7,
        "max_tokens": 350,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _call_vigilante_guardrail(user_message: str, ai_response: str) -> bool:
    """
    Agente Vigia (LLM-as-a-Judge). Avalia se a resposta da IA está dentro do escopo.
    Retorna True se estiver tudo ok, e False se houver alucinação ou desvio de contexto.
    """
    if not settings.OPENAI_API_KEY:
        return True  # Ignora o vigia se não houver API key

    url = f"{settings.OPENAI_API_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = VIGILANTE_SYSTEM_PROMPT
    
    prompt = f"Mensagem do Usuário: {user_message}\nResposta da IA: {ai_response}"
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 10,
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                result = resp.json()["choices"][0]["message"]["content"].strip().upper()
                if "ALUCINAÇÃO" in result:
                    return False
    except Exception as e:
        logger.error(f"Erro no Agente Vigia: {e}")
        # Se o vigia falhar (ex: timeout), aprova por padrão para não travar o fluxo
        pass
        
    return True


# ──────────────────────────────────────────────
# EXTRAÇÃO DE METADADOS DA RESPOSTA DA IA
# ──────────────────────────────────────────────
def _parse_confidence(text: str) -> float:
    clean_text = text.replace("**", "").replace("*", "")
    match = re.search(r'CONFIANÇA:\s*\[?(\d+)', clean_text, re.IGNORECASE)
    if match:
        return float(match.group(1)) / 100
    return 0.9


def _parse_metadata(text: str) -> dict | None:
    clean_text = text.replace("**", "").replace("*", "")
    try:
        # Tenta achar um bloco JSON válido no texto após METADADOS:
        match = re.search(r'METADADOS:\s*(?:```json)?\s*(\{.*?\})\s*(?:```)?', clean_text, re.DOTALL | re.IGNORECASE)
        json_str = None
        if match:
            json_str = match.group(1)
        else:
            # Fallback: tenta achar qualquer dicionário JSON válido
            match_fallback = re.search(r'\{.*?\}', clean_text, re.DOTALL)
            if match_fallback:
                json_str = match_fallback.group(0)
                
        if json_str:
            # Fix common JSON syntax errors generated by LLMs
            json_str = json_str.replace("True", "true").replace("False", "false").replace("None", "null")
            # Only replace single quotes if they look like JSON keys/values (naive fix)
            json_str = re.sub(r"'([^']*)'\s*:", r'"\1":', json_str)
            json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
            
            data = json.loads(json_str)
            if "name" in data or "cpf" in data or "needs_human" in data:
                return data
    except Exception as e:
        logger.error(f"Erro ao parsear metadados da IA. JSON: {json_str}. Erro: {e}")
    return None


def _remove_structured_lines(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        if "CONFIANÇA:" in line or "CONFIAŃCA:" in line or "METADADOS:" in line:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


# ──────────────────────────────────────────────
# FALLBACK SIMULADO (quando OpenAI não está disponível)
# ──────────────────────────────────────────────
def _extract_name_from_messages(user_msgs: list, cpf_re: re.Pattern) -> str | None:
    """
    Tenta extrair o nome do paciente das mensagens do usuário.
    Suporta:
    - "meu nome é Carlos", "me chamo Carlos"
    - "Carlos Portela, 05682727304" (nome junto com CPF)
    - "Carlos Portela" (nome sozinho, primeira mensagem)
    """
    # 1. Padrão com prefixo explícito
    intent_words = {
        "gostaria", "queria", "quero", "preciso", "agendar", "marcar", "consulta",
        "procedimento", "servico", "serviço", "valor", "preco", "preço", "horario",
        "horário", "limpeza", "clareamento", "implante", "canal", "restauracao",
        "restauração", "extracao", "extração", "avaliacao", "avaliação"
    }

    def is_valid_name_candidate(value: str) -> bool:
        words = [w.lower() for w in re.findall(r"[a-zA-Z\u00C0-\u00FF]+", value)]
        if len(words) < 2 or len(words) > 5:
            return False
        if any(word in intent_words for word in words):
            return False
        return len(value.strip()) >= 5 and not value.replace(" ", "").isdigit()

    prefix_pattern = re.compile(
        r"(?i)(?:\bmeu nome [eé]|\bme chamo|\baqui [eé] o|\bsou o|\bsou a|\bnome:?)\s+([a-zA-Z\s\u00C0-\u00FF]{3,50})"
    )
    for msg in user_msgs:
        m = prefix_pattern.search(msg)
        if m:
            name = m.group(1).strip().split(",")[0].strip().title()
            if is_valid_name_candidate(name):
                return name

    # 2. Nome enviado junto com CPF (ex: "carlos portela , 05682727304")
    for msg in user_msgs:
        if cpf_re.search(msg):
            # Remove o CPF e pontuação extra, o que sobra é candidato a nome
            clean = cpf_re.sub("", msg)
            clean = re.sub(r"[,\-\.\\/|:]+", " ", clean)
            clean = re.sub(r"\s+", " ", clean).strip()
            # Remove palavras-chave comuns
            clean = re.sub(
                r"(?i)\b(meu nome [eé]|me chamo|aqui [eé] o|sou o|sou a|nome|cpf|olá|ola|ei|oi)\b",
                "", clean
            ).strip()
            if is_valid_name_candidate(clean):
                return clean.title()

    # 3. Mensagem contendo apenas palavras (possível nome direto)
    for msg in user_msgs[:2]:  # olha só as primeiras mensagens
        stripped = msg.strip()
        # Se parece nome (só letras e espaços, entre 5 e 40 chars, sem números)
        if re.match(r"^[a-zA-Z\u00C0-\u00FF\s]{5,40}$", stripped) and is_valid_name_candidate(stripped):
            return stripped.title()

    return None


def _build_simulated_response(message: str, history: list) -> str:
    """Constrói uma resposta simulada quando a OpenAI não está disponível."""
    user_msgs = [h["content"] for h in history if h.get("role") == "user"] + [message]

    # Detecta CPF (normal, sem formatacao, ou censurado como 056.82*.***-**)
    cpf_re = re.compile(
        r"\d{3}\.\d{2}\*\.\*{3}-\*{2}"  # censurado: 056.82*.***-**
        r"|\d{3}\.\d{3}\.\d{3}-\d{2}"   # formatado: 056.827.273-04
        r"|\b\d{11}\b",                   # puro: 05682727304
        re.IGNORECASE
    )

    # Detecção de CPF
    cpf = None
    for msg in user_msgs:
        if cpf_re.search(msg):
            cpf = "detectado"
            break

    # Detecção de Nome (melhorada)
    name = _extract_name_from_messages(user_msgs, cpf_re)

    # Detecção de Serviço
    service = None
    services_list = ["limpeza", "clareamento", "aparelho", "implante", "canal", "restauração", "extração", "bruxismo", "faceta", "prótese"]
    services_list.extend(["restauracao", "extracao", "protese"])
    for msg in reversed(user_msgs):
        msg_l = msg.lower()
        for s in services_list:
            if s in msg_l:
                service = s.title()
                break
        if service:
            break

    # Detecção de Data/Hora
    appointment_date = None
    date_pattern = r"\b\d{1,2}/\d{1,2}(/\d{2,4})?\b|\b\d{1,2}h\d{0,2}\b|\b\d{1,2}:\d{2}\b"
    for msg in reversed(user_msgs):
        if re.search(date_pattern, msg) or any(w in msg.lower() for w in ["amanhã", "amanha", "segunda", "terça", "quarta", "quinta", "sexta", "sábado", "sabado", "hoje"]):
            match_date = re.search(r"\b\d{1,2}/\d{1,2}(/\d{2,4})?\b", msg)
            match_time = re.search(r"\b\d{1,2}:\d{2}\b|\b\d{1,2}h\b", msg)
            d = match_date.group(0) if match_date else None
            t = match_time.group(0) if match_time else "14:00"
            if d:
                appointment_date = f"o dia {d} às {t}"
            else:
                appointment_date = f"o horário sugerido das {t}"
            break

    # Verificação se upsell já foi oferecido
    offered_upsell = any(
        "Clareamento com desconto" in h.get("content", "") or "upsell" in h.get("content", "").lower()
        for h in history if h.get("role") == "assistant"
    )

    # Detecção de suporte humano
    human_keywords = ["humano", "atendente", "recepcionista", "falar com alguem", "falar com alguém", "pessoa", "suporte", "falar com um", "atendimento humano"]
    needs_human = any(kw in message.lower() for kw in human_keywords)

    simulated_metadata = {
        "name": name,
        "cpf": "detectado" if cpf else None,
        "service": service,
        "appointment_date": appointment_date,
        "slot_date": None,
        "slot_time": None,
        "upsell_success": False,
        "upsell_service": None,
        "needs_human": needs_human
    }

    # Construção da resposta
    if needs_human:
        simulated_metadata["needs_human"] = True
        response = "Sem problemas, vou chamar um de nossos atendentes para te ajudar agora mesmo! 🙏"
    elif offered_upsell:
        last = user_msgs[-1].lower() if user_msgs else ""
        if any(w in last for w in ["sim", "quero", "aceito", "pode ser", "adiciona", "com certeza", "ok", "show", "claro"]):
            simulated_metadata["upsell_success"] = True
            simulated_metadata["upsell_service"] = "Clareamento"
            response = "Que ótimo! Adicionei o Clareamento ao seu plano. A equipe da recepção vai entrar em contato para confirmar tudo. Tenha um excelente dia! ✨"
        else:
            response = f"Sem problemas! Mantive apenas a sua solicitação de {service or 'consulta'} pendente de confirmação. A equipe da recepção entrará em contato em breve para confirmar tudo. Tenha um excelente dia! ✨"
    elif name and cpf and service and appointment_date:
        response = (
            f"Perfeito! Cadastro realizado com sucesso. 🎉\n"
            f"Solicitei o agendamento de uma consulta de *{service}* para {appointment_date}.\n"
            f"Aproveita e já inclui um *Clareamento com desconto especial* junto? 😄"
        )
    elif name and cpf and service:
        response = f"Perfeito, {name}! Já registrei seu interesse em *{service}*. Qual o dia e horário de sua preferência para a consulta?"
    elif name and cpf:
        response = f"Ótimo, {name}! Agora me diz: qual procedimento você tem interesse? Temos Limpeza, Clareamento, Implante e muito mais!"
    elif service:
        response = "Perfeito! Para eu agilizar seu cadastro, me informe seu Nome Completo e CPF em uma única mensagem. 😊"
    elif name:
        response = f"Prazer, {name}! 😊 Para eu fazer seu cadastro na recepção, poderia me informar o seu CPF?"
    elif cpf:
        response = "Perfeito! E qual é o seu nome completo para finalizarmos o cadastro?"
    else:
        if not history:
            response = (
                "Olá! 👋✨\n"
                "Seja bem-vindo(a) à Lumina Clínica Odontológica 🦷✨\n\n"
                "Será um prazer cuidar do seu sorriso!\n\n"
                "Como podemos te ajudar hoje?"
            )
        else:
            response = (
                "Como posso ajudar? Para iniciarmos o agendamento, "
                "por favor me informe seu *Nome Completo e CPF*."
            )

    return (
        f"{response}\n\n"
        f"CONFIANÇA: 95\n"
        f"METADADOS: {json.dumps(simulated_metadata, ensure_ascii=False)}"
    )


def _normalize_service_name(value: str | None) -> set[str]:
    if not value:
        return set()
    normalized = unicodedata.normalize("NFD", value.lower())
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    words = re.findall(r"[a-z0-9]+", normalized)
    stopwords = {"de", "da", "do", "das", "dos", "por", "para", "com", "em", "a", "o", "e", "sessao"}
    return {word for word in words if len(word) > 2 and word not in stopwords}


def _services_are_similar(primary_service: str | None, upsell_service: str | None) -> bool:
    primary_words = _normalize_service_name(primary_service)
    upsell_words = _normalize_service_name(upsell_service)
    if not primary_words or not upsell_words:
        return False
    overlap = primary_words & upsell_words
    return bool(overlap) or primary_words.issubset(upsell_words) or upsell_words.issubset(primary_words)


def _remove_upsell_offer_text(clean_text: str, upsell_service: str) -> str:
    paragraphs = re.split(r"\n\s*\n", clean_text.strip())
    kept = [
        paragraph for paragraph in paragraphs
        if upsell_service.lower() not in paragraph.lower()
        and "aproveitando" not in paragraph.lower()
        and "complemento" not in paragraph.lower()
        and "serviço adicional" not in paragraph.lower()
        and "servico adicional" not in paragraph.lower()
    ]
    return "\n\n".join(kept).strip() or clean_text


def apply_upsell_guardrail(clean_text: str, metadata: dict | None, valid_exam_names: list[str]) -> tuple[str, dict | None]:
    """Valida o serviço de upsell sugerido pela IA contra os exames reais do banco."""
    if not metadata or not metadata.get("upsell_service"):
        return clean_text, metadata

    upsell_service = metadata["upsell_service"]
    primary_service = metadata.get("service")
    
    # Verifica se o serviço de upsell existe nos exames do banco (case insensitive)
    matched_exam = None
    for exam_name in valid_exam_names:
        if upsell_service.lower() in exam_name.lower() or exam_name.lower() in upsell_service.lower():
            matched_exam = exam_name
            break
            
    if matched_exam:
        metadata["upsell_service"] = matched_exam
    else:
        # Se não existe, escolhe um de prevenção da lista
        fallback_exam = None
        for name in ["Limpeza", "Clareamento", "Consulta Geral", "Prevenção"]:
            for exam_name in valid_exam_names:
                if name.lower() in exam_name.lower():
                    fallback_exam = exam_name
                    break
            if fallback_exam:
                break
        
        if not fallback_exam and valid_exam_names:
            fallback_exam = valid_exam_names[0]
            
        if fallback_exam:
            logger.warning(f"Guardrail de Upsell: Substituindo serviço hallucinado '{upsell_service}' por '{fallback_exam}'")
            # Substitui no texto da resposta também
            pattern = re.compile(re.escape(upsell_service), re.IGNORECASE)
            clean_text = pattern.sub(fallback_exam, clean_text)
            metadata["upsell_service"] = fallback_exam
        else:
            metadata["upsell_success"] = False
            metadata["upsell_service"] = None

    final_upsell = metadata.get("upsell_service")
    if final_upsell and _services_are_similar(primary_service, final_upsell):
        logger.warning(f"Guardrail de Upsell: removendo upsell igual ao serviço principal '{primary_service}' -> '{final_upsell}'")
        clean_text = _remove_upsell_offer_text(clean_text, final_upsell)
        metadata["upsell_success"] = False
        metadata["upsell_service"] = None

    return clean_text, metadata


# ──────────────────────────────────────────────
# FUNÇÃO PRINCIPAL
# ──────────────────────────────────────────────
async def get_response(message: str, history: list, faq_context: str = "", media: dict = None) -> tuple[str, float, dict | None]:
    # 1. Input Guardrail: detecta jailbreak
    if detect_jailbreak(message):
        logger.warning(f"Jailbreak detectado: '{message[:50]}'")
        fallback_msg = (
            "Olá! Sou a Lúmina, atendente virtual da Clínica Lúmina. 😊\n\n"
            "Estou aqui para esclarecer suas dúvidas sobre nossos procedimentos odontológicos "
            "e ajudar você a agendar um horário. Como posso ajudar?"
        )
        return fallback_msg, 1.0, None

    # 2. Carrega exames do banco para o contexto da IA
    services_context = ""
    valid_exam_names = []
    try:
        async with AsyncSession() as session:
            res = await session.execute(select(ExamWeb))
            exams = res.scalars().all()
            if exams:
                valid_exam_names = [e.name for e in exams]
                services_context = "\n\nProcedimentos e Exames Disponíveis na Clínica Lúmina (Valores a Partir De):\n"
                for e in exams:
                    services_context += f"- {e.name} (Valor: A partir de R$ {e.price:.2f}) [Categoria: {e.category}]\n"
                services_context += "\nNÃO liste todos esses serviços no chat. Use essa tabela APENAS para consulta interna caso o paciente pergunte o preço de algo específico ou para oferecer upsell quando pertinente!"
    except Exception as e:
        logger.error(f"Erro ao carregar exames do banco: {e}")

    # 2b. Carrega slots disponíveis da agenda
    slots_context = ""
    try:
        slots_context = await get_available_slots_context(days_ahead=7)
    except Exception as e:
        logger.error(f"Erro ao carregar slots de agenda: {e}")

    # 3. Monta o system prompt completo
    system = (
        SYSTEM_PROMPT
        + "\n\nREGRA DE HORARIO: O horario correto de funcionamento e segunda a sexta, "
        "das 08h00 as 12h00 e das 14h00 as 18h00. Nunca ofereca nem aceite horarios "
        "no intervalo de almoco, como 12h, 13h ou 13h30."
        "\nREGRA DE PRECO: Se o paciente perguntar o valor/preco de um procedimento "
        "especifico, responda diretamente com o valor desse procedimento usando a lista oficial. "
        "Nao diga que vai enviar PDF/tabela nesse caso."
    )
    if services_context:
        system += services_context
    if slots_context:
        system += slots_context
    if faq_context:
        system += f"\n\n{faq_context}"

    messages = history + [{"role": "user", "content": message}]

    # 4. Orquestração da Redundância (Fallback por Timeout)
    text = None
    primary_task = asyncio.create_task(_call_openai(system, messages, media))
    
    try:
        logger.info(f"Chamando Agente Primário ({settings.OPENAI_MODEL}) com timeout de {settings.AI_TIMEOUT_SECONDS}s...")
        # Espera o Agente Primário até o tempo limite
        text = await asyncio.wait_for(primary_task, timeout=settings.AI_TIMEOUT_SECONDS)
        logger.info("Agente Primário respondeu com sucesso dentro do tempo limite.")
    except asyncio.TimeoutError:
        logger.warning(f"⏰ Agente Primário estourou o tempo limite de {settings.AI_TIMEOUT_SECONDS}s! Disparando Agente Secundário (Dedo no Gatilho).")
        # Primário engasgou. Deixamos ele rodando no background e disparamos o Secundário.
        secondary_task = asyncio.create_task(_call_secondary_ai(system, messages))
        
        # Agora faremos uma corrida: quem terminar primeiro ganha (Primário atrasado vs Secundário novo)
        done, pending = await asyncio.wait(
            [primary_task, secondary_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Pega o resultado do vencedor
        winner = done.pop()
        try:
            text = winner.result()
            if winner == primary_task:
                logger.info("Agente Primário finalmente respondeu e venceu a corrida do atraso.")
            else:
                logger.info(f"Agente Secundário ({settings.SECONDARY_AI_MODEL}) salvou o dia!")
        except Exception as e:
            logger.warning(f"Erro no vencedor da corrida: {e}")
            
        # Cancela o perdedor para economizar recursos
        for p in pending:
            p.cancel()
    except Exception as e:
        logger.warning(f"Erro imediato no Agente Primário: {e}. Disparando Agente Secundário.")
        try:
            text = await _call_secondary_ai(system, messages)
        except Exception as sec_e:
            logger.error(f"Erro no Agente Secundário: {sec_e}")

    # 5. Fallback simulado se OpenAI não disponível
    if text is None:
        text = _build_simulated_response(message, history)

    # 6. Parseia e limpa a resposta
    logger.info(f"TEXTO BRUTO DA IA:\n{text}")
    confidence = _parse_confidence(text)
    metadata = _parse_metadata(text) or {}
    clean = _remove_structured_lines(text)
    clean = validate_output_guardrail(clean)

    # 8. Aplica guardrail de upsell para evitar serviços inexistentes/hallucinados
    clean, metadata = apply_upsell_guardrail(clean, metadata, valid_exam_names)

    logger.info(f"IA respondeu | confianca={confidence:.2f} | metadata={metadata}")
    return clean, confidence, metadata


async def audit_response_in_background(message: str, ai_response: str):
    """
    Auditoria assíncrona do Agente Vigia. Chamada DEPOIS que a resposta já foi enviada.
    Se detectar alucinação, apenas loga o warning (não bloqueia o usuário).
    """
    try:
        is_approved = await _call_vigilante_guardrail(message, ai_response)
        if not is_approved:
            logger.warning(f"[VIGIA PÓS-ENVIO] Alucinação detectada na resposta enviada! msg='{message[:50]}'")
    except Exception as e:
        logger.error(f"Erro no Agente Vigia em background: {e}")
