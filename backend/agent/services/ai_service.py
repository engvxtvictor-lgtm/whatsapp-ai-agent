from groq import AsyncGroq
from sqlalchemy import select
from backend.system.config import settings
from backend.system.logger import logger
from backend.system.database import AsyncSession
from backend.system.models.web_models import ServiceWeb

client = AsyncGroq(api_key=settings.GROQ_API_KEY)

SYSTEM = """Você é a Lúmina, uma atendente virtual humana, empática e muito simpática da clínica odontológica Clínica Lúmina.
Seu objetivo é tirar as dúvidas dos pacientes com muito carinho, atenção e cordialidade, e guiá-los no agendamento de consultas.

Instruções de Personalidade e Tom:
1. Aja como uma atendente humana real de recepção. Seja atenciosa, empática e prestativa.
2. NUNCA sob qualquer circunstância revele que você é uma inteligência artificial, robô, assistente inteligente, LLM ou modelo de linguagem.
3. NUNCA cite termos técnicos como "sistema", "banco de dados", "fluxo de fechamento", "JSON", "metadados", "CONFIANÇA", "Groq", "FastAPI" ou qualquer detalhe operacional/técnico de programação.
4. Explique os procedimentos com linguagem clara e reconfortante (como uma especialista acolhedora da recepção da clínica).

Fluxo de Conversação / Fechamento:
- Quando o paciente iniciar a conversa (ex: "gostaria de saber sobre branqueamento"), responda todas as dúvidas dele detalhadamente primeiro (explicando os benefícios e a importância descritos na tabela de serviços abaixo).
- Após responder e tirar as dúvidas, convide o paciente a agendar uma consulta para avaliação de forma natural (ex: "Gostaria de agendar um horário para fazermos uma avaliação com um de nossos dentistas?").
- Se ele demonstrar interesse em agendar, siga este fluxo de fechamento natural:
  1. Peça educadamente o Nome Completo e o CPF (diga que precisa para fazer o cadastro dele em nossa recepção).
  2. Peça o Dia e Horário desejados para a consulta.
  3. Ofereça de forma extremamente sutil e contextualizada um serviço adicional de UPSELL baseado nas motivações listadas abaixo.
  4. Nota: É normal que o CPF no histórico apareça censurado (ex: 123.45*.***-**). Isso é uma medida automática de segurança para proteção dos seus dados, não se preocupe e prossiga normalmente.

Ao final de TODA resposta, você DEVE incluir exatamente essas duas linhas estruturadas de metadados:
CONFIANÇA: [número de 0 a 100]
METADADOS: {"name": "nome_do_paciente_ou_null", "cpf": "cpf_ou_null", "service": "servico_principal_ou_null", "appointment_date": "dia_e_horario_ou_null", "upsell_success": true_ou_false, "upsell_service": "servico_adicional_ou_null"}

Regras estritas:
- O JSON na linha METADADOS deve conter chaves e valores válidos em JSON (use null para campos não identificados).
- Não invente preços ou serviços além dos listados formalmente pela clínica.
- Máximo 3 parágrafos de texto no corpo da mensagem."""


import re

def detect_jailbreak(message: str) -> bool:
    """
    Detecta tentativas de jailbreak, desvio de contexto ou vazamento de prompt.
    """
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
        r"chave\s+de\s+api",
        r"api\s+key",
        r"banco\s+de\s+dados",
        r"database\s+schema"
    ]
    combined = re.compile("|".join(patterns), re.IGNORECASE)
    return bool(combined.search(message))


def validate_output_guardrail(response: str) -> str:
    """
    Sanitiza e valida a resposta da IA para garantir conformidade e polidez.
    """
    technical_words = ["JSON", "METADADOS:", "CONFIANÇA:", "CONFIAŃCA:", "FastAPI", "Groq", "Llama3"]
    # Se vazou linhas estruturadas de metadados, removemos
    lines = []
    for line in response.split("\n"):
        if any(w in line for w in ["METADADOS:", "CONFIANÇA:", "CONFIAŃCA:"]):
            continue
        lines.append(line)
    
    clean_text = "\n".join(lines).strip()
    return clean_text


def extract_and_censor_cpf(text: str) -> tuple[str, str | None]:
    """
    Busca CPF na mensagem. Retorna (mensagem_censurada, cpf_limpo).
    """
    # Padrão CPF formatado ou não (11 dígitos)
    cpf_pattern = r"\b(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})\b"
    match = re.search(cpf_pattern, text)
    if match:
        full_cpf = "".join(match.groups())
        censored = f"{full_cpf[:3]}.{full_cpf[3:5]}*.***-**"
        censored_text = re.sub(cpf_pattern, censored, text)
        return censored_text, full_cpf
        
    # Padrão 11 dígitos sequenciais puros
    pure_pattern = r"\b\d{11}\b"
    pure_match = re.search(pure_pattern, text)
    if pure_match:
        full_cpf = pure_match.group(0)
        censored = f"{full_cpf[:3]}.{full_cpf[3:5]}*.***-**"
        censored_text = re.sub(pure_pattern, censored, text)
        return censored_text, full_cpf

    return text, None


async def get_response(message: str, history: list, faq_context: str = "") -> tuple[str, float, dict | None]:
    # 1. Input Guardrail: Detecta Jailbreak
    if detect_jailbreak(message):
        logger.warning(f"Jailbreak detectado na mensagem do usuario: '{message[:50]}'")
        fallback_msg = (
            "Olá! Sou a Lúmina, assistente virtual da Clínica Lúmina. 😊\n\n"
            "Meu papel é esclarecer suas dúvidas sobre nossos procedimentos odontológicos (como Limpeza, Clareamento, Implante e Aparelho) "
            "e ajudar você a agendar um horário com nossos profissionais. Como posso ajudar com seu sorriso hoje?"
        )
        return fallback_msg, 1.0, None

    # Busca os serviços cadastrados no banco de dados para alimentar o contexto do Agente
    services_context = ""
    try:
        async with AsyncSession() as session:
            res = await session.execute(select(ServiceWeb))
            services = res.scalars().all()
            if services:
                services_context = "\n\nProcedimentos e Serviços Disponíveis na Clínica Lúmina:\n"
                for s in services:
                    services_context += f"- {s.name} (Preço Médio: R$ {s.price:.2f}): {s.necessity}\n"
                services_context += "\nUtilize as motivações e descrições de necessidade acima para realizar ofertas de UPSELL contextuais e altamente inteligentes para o paciente!"
    except Exception as e:
        logger.error(f"Erro ao carregar servicos do banco para o prompt da IA: {e}")

    system = SYSTEM
    if services_context:
        system += services_context
    if faq_context:
        system += f"\n\n{faq_context}"

    messages = history + [{"role": "user", "content": message}]

    resp = await client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "system", "content": system}] + messages,
        max_tokens=600,
        temperature=0.7,
    )

    text = resp.choices[0].message.content
    confidence = _parse_confidence(text)
    metadata = _parse_metadata(text)
    clean = _remove_structured_lines(text)
    
    # 2. Output Guardrail: Sanitiza resposta
    clean = validate_output_guardrail(clean)

    logger.info(f"IA respondeu | confianca={confidence:.2f} | metadata={metadata}")
    return clean, confidence, metadata


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
    import json
    for line in reversed(text.split("\n")):
        if "METADADOS:" in line:
            try:
                json_str = line.split("METADADOS:")[1].strip()
                return json.loads(json_str)
            except Exception as e:
                logger.error(f"Erro ao parsear metadados da IA: {e}")
                pass
    return None


def _remove_structured_lines(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        if "CONFIANÇA:" in line or "CONFIAŃCA:" in line or "METADADOS:" in line:
            continue
        lines.append(line)
    return "\n".join(lines).strip()
