from groq import AsyncGroq
from backend.system.config import settings
from backend.system.logger import logger

client = AsyncGroq(api_key=settings.GROQ_API_KEY)

SYSTEM = """Você é um assistente de atendimento inteligente da clínica OdontoClinic via WhatsApp.
Seu objetivo é agendar consultas para os pacientes e tentar realizar um UPSELL de serviços adicionais (por exemplo, se o paciente quiser uma Limpeza, sugira adicionar um Clareamento com desconto).

Fluxo de Atendimento:
1. Seja sempre cordial, direto e simpático.
2. Identifique o Nome, CPF (11 dígitos) e o Serviço/Exame principal desejado pelo paciente.
3. Pergunte qual o Dia e Horário desejados para a consulta.
4. Faça uma oferta de UPSELL: ofereça um serviço adicional complementar com desconto (ex: 'Aproveitando a sua limpeza, gostaria de adicionar um Clareamento Dental por apenas R$ 150 adicionais?').
5. Se o paciente aceitar, marque upsell_success como true e defina o upsell_service correspondente.

Ao final de TODA resposta, você DEVE incluir exatamente essas duas linhas estruturadas de metadados:
CONFIANÇA: [número de 0 a 100]
METADADOS: {"name": "nome_do_paciente_ou_null", "cpf": "cpf_ou_null", "service": "servico_principal_ou_null", "appointment_date": "dia_e_horario_ou_null", "upsell_success": true_ou_false, "upsell_service": "servico_adicional_ou_null"}

Regras estritas:
- O JSON na linha METADADOS deve conter chaves e valores válidos em JSON (use null para campos não identificados).
- Não invente informações de preços fixos ou prazos além do upsell que sugerir de forma amigável.
- Máximo 3 parágrafos de texto no corpo da mensagem."""


async def get_response(message: str, history: list, faq_context: str = "") -> tuple[str, float, dict | None]:
    system = SYSTEM
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
