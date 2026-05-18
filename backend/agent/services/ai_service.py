from groq import AsyncGroq
from backend.system.config import settings
from backend.system.logger import logger

client = AsyncGroq(api_key=settings.GROQ_API_KEY)

SYSTEM = """Você é um assistente de atendimento via WhatsApp. Seja cordial e direto.

Regras:
- Responda em português brasileiro
- Máximo 3 parágrafos curtos
- Se não souber, diga que vai transferir pra um atendente
- Nunca invente preços, prazos ou informações

Ao final de cada resposta, inclua exatamente essa linha:
CONFIANÇA: [número de 0 a 100]"""


async def get_response(message: str, history: list, faq_context: str = "") -> tuple[str, float]:
    system = SYSTEM
    if faq_context:
        system += f"\n\n{faq_context}"

    messages = history + [{"role": "user", "content": message}]

    resp = await client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "system", "content": system}] + messages,
        max_tokens=500,
        temperature=0.7,
    )

    text = resp.choices[0].message.content
    confidence = _parse_confidence(text)
    clean = _remove_confidence_line(text)

    logger.info(f"IA respondeu | confiança={confidence:.2f}")
    return clean, confidence


def _parse_confidence(text: str) -> float:
    for line in reversed(text.split("\n")):
        if "CONFIANÇA:" in line:
            try:
                return float(line.split(":")[1].strip()) / 100
            except Exception:
                pass
    return 0.5


def _remove_confidence_line(text: str) -> str:
    return "\n".join(l for l in text.split("\n") if "CONFIANÇA:" not in l).strip()
