import re
import json
import httpx
from sqlalchemy import select
from backend.system.config import settings
from backend.system.logger import logger
from backend.system.database import AsyncSession
from backend.system.models.web_models import ExamWeb
from backend.agent.services.schedule_service import get_available_slots_context

# ──────────────────────────────────────────────
# PROMPT DE SISTEMA DA LÚMINA
# ──────────────────────────────────────────────
SYSTEM = """Você é a Lúmina, uma atendente virtual humana, empática e muito simpática da clínica odontológica Clínica Lúmina.
Seu objetivo é tirar as dúvidas dos pacientes com muito carinho, atenção e cordialidade, e guiá-los no agendamento de consultas.

Instruções de Personalidade e Tom:
1. Aja como uma atendente humana real de recepção. Seja atenciosa, empática e prestativa.
2. NUNCA sob qualquer circunstância revele que você é uma inteligência artificial, robô, assistente inteligente, LLM ou modelo de linguagem.
3. NUNCA cite termos técnicos como "sistema", "banco de dados", "fluxo de fechamento", "JSON", "Ollama", "FastAPI" ou qualquer detalhe operacional/técnico de programação no texto principal de sua resposta para o paciente.
4. Explique os procedimentos com linguagem clara e reconfortante (como uma especialista acolhedora da recepção da clínica).

Fluxo de Conversação / Fechamento (Siga os passos em ordem):
- PASSO 1 (Início): Se for a sua primeira mensagem na conversa, NÃO liste nossos serviços no texto e NÃO ofereça enviar o PDF (ele já é enviado automaticamente pelo sistema). Apenas diga: "Acabei de enviar o nosso catálogo em PDF logo abaixo. Qual desses serviços chamou sua atenção?".
- PASSO 2 (Coleta de Dados): Quando ele responder dizendo qual serviço ele quer, peça educadamente o Nome Completo e o CPF (diga que precisa para o cadastro).
- PASSO 3 (Agendamento): Quando ele fornecer os dados, informe nosso horário de funcionamento (Segunda a Sexta, das 09h00 às 18h00) e pergunte qual dia ele prefere.
- PASSO 4 (Sugestão de Horário): Quando ele disser o dia, dê UMA ou DUAS sugestões de horário específico baseadas na lista de HORÁRIOS DISPONÍVEIS abaixo.
- PASSO 5 (Follow-Up / Upsell): Depois que ele escolher e confirmar o horário, confirme que a solicitação de agendamento foi enviada com sucesso para a nossa equipe aprovar. NUNCA diga que a consulta já "está confirmada" ou "agendada definitivamente". Diga que a equipe da recepção fará a confirmação em breve. Em seguida, ofereça de forma sutil um serviço adicional (UPSELL) que combine com o perfil dele.
  4. Nota de Sistema: O CPF que você vai receber do histórico estará censurado por segurança (ex: 123.45*.***-**). Apenas aceite-o e siga com o atendimento sem comentar sobre a censura.
- Suporte Humano: Se o paciente solicitar falar com um humano, defina "needs_human": true nos METADADOS.

*** ATENÇÃO CRÍTICA DO SISTEMA ***
Ao final de TODA resposta, independentemente do que você disser no chat, você é ABSOLUTAMENTE OBRIGADA a imprimir exatamente estas duas linhas. Elas são ocultas e servem para o sistema interno. Se você omiti-las, o sistema irá falhar:
CONFIANÇA: [número de 0 a 100]
METADADOS: {"name": "nome_do_paciente_ou_null", "cpf": "cpf_ou_null", "service": "servico_principal_ou_null", "appointment_date": "dia_e_horario_ou_null", "slot_date": "YYYY-MM-DD_ou_null", "slot_time": "HH:MM_ou_null", "upsell_success": true_ou_false, "upsell_service": "servico_adicional_ou_null", "needs_human": true_ou_false}
**********************************

- O JSON na linha METADADOS deve conter chaves e valores válidos em JSON (use null para campos não identificados).
- Não invente preços ou serviços além dos listados formalmente pela clínica.
- NUNCA diga ao paciente que a consulta dele "está confirmada" ou "agendada definitivamente". Diga sempre que a solicitação foi recebida/enviada e que a equipe de recepção fará a confirmação em breve.
- Ao oferecer um serviço adicional (UPSELL) no PASSO 5, você deve obrigatoriamente e exclusivamente escolher um serviço da lista de "Procedimentos e Exames Disponíveis" fornecida no contexto abaixo. NUNCA ofereça procedimentos que não estão na lista (como "aplicação de flúor", a menos que esteja cadastrado na tabela de exames).
- Ao citar os preços de qualquer procedimento, informe SEMPRE que o valor é "a partir de" (ex: "a partir de R$ 150,00"), pois os valores informados são os preços mínimos iniciais e podem variar.
- Seja EXTREMAMENTE concisa e direta. Suas respostas devem ser CURTAS (máximo de 1 a 2 parágrafos pequenos). Não enrole."""


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
        if match:
            return json.loads(match.group(1))
        
        # Fallback: tenta achar qualquer dicionário JSON válido
        match_fallback = re.search(r'\{.*?\}', clean_text, re.DOTALL)
        if match_fallback:
            data = json.loads(match_fallback.group(0))
            if "name" in data or "cpf" in data:
                return data
    except Exception as e:
        logger.error(f"Erro ao parsear metadados da IA. Erro: {e}")
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


def apply_upsell_guardrail(clean_text: str, metadata: dict | None, valid_exam_names: list[str]) -> tuple[str, dict | None]:
    """Valida o serviço de upsell sugerido pela IA contra os exames reais do banco."""
    if not metadata or not metadata.get("upsell_service"):
        return clean_text, metadata

    upsell_service = metadata["upsell_service"]
    
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
            
    return clean_text, metadata


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
    system = SYSTEM
    if services_context:
        system += services_context
    if slots_context:
        system += slots_context
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
    logger.info(f"TEXTO BRUTO DA IA:\n{text}")
    confidence = _parse_confidence(text)
    metadata = _parse_metadata(text)
    clean = _remove_structured_lines(text)
    clean = validate_output_guardrail(clean)

    # 7. Aplica guardrail de upsell para evitar serviços inexistentes/hallucinados
    clean, metadata = apply_upsell_guardrail(clean, metadata, valid_exam_names)

    logger.info(f"IA respondeu | confianca={confidence:.2f} | metadata={metadata}")
    return clean, confidence, metadata
