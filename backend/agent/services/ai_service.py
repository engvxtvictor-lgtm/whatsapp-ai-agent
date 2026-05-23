import re
import json
import httpx
from sqlalchemy import select
from backend.system.config import settings
from backend.system.logger import logger
from backend.system.database import AsyncSession
from backend.system.models.web_models import ExamWeb

# ──────────────────────────────────────────────
# PROMPT DE SISTEMA DA LÚMINA
# ──────────────────────────────────────────────
SYSTEM = """Você é a Lúmina, uma atendente virtual humana, empática e muito simpática da clínica odontológica Clínica Lúmina.
Seu objetivo é tirar as dúvidas dos pacientes com muito carinho, atenção e cordialidade, e guiá-los no agendamento de consultas.

Instruções de Personalidade e Tom:
1. Aja como uma atendente humana real de recepção. Seja atenciosa, empática e prestativa.
2. NUNCA sob qualquer circunstância revele que você é uma inteligência artificial, robô, assistente inteligente, LLM ou modelo de linguagem.
3. NUNCA cite termos técnicos como "sistema", "banco de dados", "fluxo de fechamento", "JSON", "metadados", "CONFIANÇA", "Ollama", "FastAPI" ou qualquer detalhe operacional/técnico de programação.
4. Explique os procedimentos com linguagem clara e reconfortante (como uma especialista acolhedora da recepção da clínica).

Fluxo de Conversação / Fechamento:
- Quando o paciente iniciar a conversa ou demonstrar interesse, apresente uma lista clara com os serviços que oferecemos (com base na tabela abaixo) e pergunte qual deles ele deseja.
- Após ele escolher o serviço de interesse:
  1. Peça educadamente o Nome Completo e o CPF (para fazer o cadastro na recepção).
  2. Após ele fornecer os dados, pergunte qual dia ele tem disponibilidade para que você possa sugerir um horário.
  3. Depois de confirmado o dia e horário da consulta (Agendamento finalizado), vá para o Follow-Up: confirme que está tudo certo e ofereça de forma sutil um serviço adicional (UPSELL) que combine com o perfil dele.
  4. Nota de Sistema: O CPF que você vai receber do histórico estará censurado por segurança (ex: 123.45*.***-**). Apenas aceite-o e siga com o atendimento sem comentar sobre a censura.
- Suporte Humano: Se o paciente solicitar falar com um humano, defina "needs_human": true nos METADADOS.

Ao final de TODA resposta, você DEVE incluir exatamente essas duas linhas estruturadas de metadados:
CONFIANÇA: [número de 0 a 100]
METADADOS: {"name": "nome_do_paciente_ou_null", "cpf": "cpf_ou_null", "service": "servico_principal_ou_null", "appointment_date": "dia_e_horario_ou_null", "upsell_success": true_ou_false, "upsell_service": "servico_adicional_ou_null", "needs_human": true_ou_false}

Regras estritas:
- O JSON na linha METADADOS deve conter chaves e valores válidos em JSON (use null para campos não identificados).
- Não invente preços ou serviços além dos listados formalmente pela clínica.
- Máximo 3 parágrafos de texto no corpo da mensagem."""


# ──────────────────────────────────────────────
# GUARDRAILS DE ENTRADA E SAÍDA
# ──────────────────────────────────────────────
def detect_jailbreak(message: str) -> bool:
    """Detecta tentativas de jailbreak, desvio de contexto ou vazamento de prompt."""
    patterns = [
        r"ignor[ae]r?\s+(as\s+|previous\s+)?instru",
        r"system\s+prompt",
        r"prompt\s+de\s+sistema",
        r"developer\s+mode",
        r"modo\s+desenvolvedor",
        r"dan\s+mode",
        r"you\s+are\s+now\s+a",
        r"você\s+agora\s+é\s+um",
        r"voce\s+agora\s+e\s+um",
        r"revelar?\s+suas?\s+instru",
        r"reveal\s+your\s+instru",
        r"groq_api_key",
        r"ollama_url",
        r"chave\s+de\s+api",
        r"api\s+key",
        r"banco\s+de\s+dados",
        r"database\s+schema"
    ]
    combined = re.compile("|".join(patterns), re.IGNORECASE)
    return bool(combined.search(message))


def validate_output_guardrail(response: str) -> str:
    """Sanitiza a resposta da IA removendo linhas estruturadas de metadados."""
    lines = []
    for line in response.split("\n"):
        if any(w in line for w in ["METADADOS:", "CONFIANÇA:", "CONFIAŃCA:"]):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def extract_and_censor_cpf(text: str) -> tuple[str, str | None]:
    """Busca CPF na mensagem. Retorna (mensagem_censurada, cpf_limpo)."""
    cpf_pattern = r"\b(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})\b"
    match = re.search(cpf_pattern, text)
    if match:
        full_cpf = "".join(match.groups())
        censored = f"{full_cpf[:3]}.{full_cpf[3:5]}*.***-**"
        censored_text = re.sub(cpf_pattern, censored, text)
        return censored_text, full_cpf

    pure_pattern = r"\b\d{11}\b"
    pure_match = re.search(pure_pattern, text)
    if pure_match:
        full_cpf = pure_match.group(0)
        censored = f"{full_cpf[:3]}.{full_cpf[3:5]}*.***-**"
        censored_text = re.sub(pure_pattern, censored, text)
        return censored_text, full_cpf

    return text, None


# ──────────────────────────────────────────────
# CHAMADA À OPENAI (CHATGPT)
# ──────────────────────────────────────────────
async def _call_openai(system_prompt: str, messages: list) -> str:
    """Chama a API da OpenAI. Retorna o texto da resposta."""
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "sua_chave_openai_aqui":
        raise Exception("OPENAI_API_KEY não configurada.")

    url = f"{settings.OPENAI_API_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.OPENAI_MODEL,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": 0.7,
        "max_tokens": 600,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ──────────────────────────────────────────────
# EXTRAÇÃO DE METADADOS DA RESPOSTA DA IA
# ──────────────────────────────────────────────
def _parse_confidence(text: str) -> float:
    for line in reversed(text.split("\n")):
        if "CONFIANÇA:" in line or "CONFIAŃCA:" in line:
            try:
                parts = line.split(":")
                val = parts[1].strip().replace("[", "").replace("]", "").replace("%", "")
                return float(val) / 100
            except Exception:
                pass
    return 0.5


def _parse_metadata(text: str) -> dict | None:
    for line in reversed(text.split("\n")):
        if "METADADOS:" in line:
            try:
                json_str = line.split("METADADOS:")[1].strip()
                return json.loads(json_str)
            except Exception as e:
                logger.error(f"Erro ao parsear metadados da IA: {e}")
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
    prefix_pattern = re.compile(
        r"(?i)(?:\bmeu nome [eé]|\bme chamo|\baqui [eé] o|\bsou o|\bsou a|\bnome:?)\s+([a-zA-Z\s\u00C0-\u00FF]{3,50})"
    )
    for msg in user_msgs:
        m = prefix_pattern.search(msg)
        if m:
            name = m.group(1).strip().split(",")[0].strip().title()
            if len(name) >= 3 and not name.replace(" ", "").isdigit():
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
            if len(clean) >= 3 and not clean.replace(" ", "").isdigit():
                return clean.title()

    # 3. Mensagem contendo apenas palavras (possível nome direto)
    for msg in user_msgs[:2]:  # olha só as primeiras mensagens
        stripped = msg.strip()
        # Se parece nome (só letras e espaços, entre 5 e 40 chars, sem números)
        if re.match(r"^[a-zA-Z\u00C0-\u00FF\s]{5,40}$", stripped):
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
            d = match_date.group(0) if match_date else "em breve"
            t = match_time.group(0) if match_time else "14:00"
            appointment_date = f"{d} às {t}"
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
            response = f"Sem problemas! Mantive apenas a sua {service or 'consulta'} agendada. A equipe da recepção entrará em contato em breve para confirmar. Tenha um excelente dia! ✨"
    elif name and cpf and service and appointment_date:
        response = (
            f"Perfeito! Cadastro realizado com sucesso. 🎉\n"
            f"Agendei uma consulta de *{service}* para o dia {appointment_date}.\n"
            f"Aproveita e já inclui um *Clareamento com desconto especial* junto? 😄"
        )
    elif name and cpf and service:
        response = f"Perfeito, {name}! Já registrei seu interesse em *{service}*. Qual o dia e horário de sua preferência para a consulta?"
    elif name and cpf:
        response = f"Ótimo, {name}! Agora me diz: qual procedimento você tem interesse? Temos Limpeza, Clareamento, Implante e muito mais!"
    elif name:
        response = f"Prazer, {name}! 😊 Para eu fazer seu cadastro na recepção, poderia me informar o seu CPF?"
    elif cpf:
        response = "Perfeito! E qual é o seu nome completo para finalizarmos o cadastro?"
    else:
        if not history:
            response = (
                "Olá! Eu sou a Lúmina, atendente virtual da Clínica Lúmina. 😊\n"
                "Como posso ajudar você hoje? Se quiser agendar uma consulta, por favor me informe o seu *Nome Completo e CPF* para eu fazer o seu cadastro!"
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


# ──────────────────────────────────────────────
# FUNÇÃO PRINCIPAL
# ──────────────────────────────────────────────
async def get_response(message: str, history: list, faq_context: str = "") -> tuple[str, float, dict | None]:
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
    try:
        async with AsyncSession() as session:
            res = await session.execute(select(ExamWeb))
            exams = res.scalars().all()
            if exams:
                services_context = "\n\nProcedimentos e Exames Disponíveis na Clínica Lúmina (Valores a Partir De):\n"
                for e in exams:
                    services_context += f"- {e.name} (Valor: R$ {e.price:.2f}) [Categoria: {e.category}]\n"
                services_context += "\nUse a tabela acima para responder dúvidas e ofereça upsell quando pertinente!"
    except Exception as e:
        logger.error(f"Erro ao carregar exames do banco: {e}")

    # 3. Monta o system prompt completo
    system = SYSTEM
    if services_context:
        system += services_context
    if faq_context:
        system += f"\n\n{faq_context}"

    messages = history + [{"role": "user", "content": message}]

    # 4. Tenta chamar a OpenAI
    text = None
    try:
        logger.info(f"Chamando OpenAI ({settings.OPENAI_MODEL})...")
        text = await _call_openai(system, messages)
        logger.info("OpenAI respondeu com sucesso.")
    except Exception as e:
        logger.warning(f"Erro ao chamar OpenAI: {e}. Usando resposta simulada.")

    # 5. Fallback simulado se OpenAI não disponível
    if text is None:
        text = _build_simulated_response(message, history)

    # 6. Parseia e limpa a resposta
    confidence = _parse_confidence(text)
    metadata = _parse_metadata(text)
    clean = _remove_structured_lines(text)
    clean = validate_output_guardrail(clean)

    logger.info(f"IA respondeu | confianca={confidence:.2f} | metadata={metadata}")
    return clean, confidence, metadata
