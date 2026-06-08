import re

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


def _format_cpf(digits: str) -> str:
    """Formata 11 dígitos como CPF: XXX.XXX.XXX-XX"""
    d = digits.zfill(11)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"


def extract_and_censor_cpf(text: str) -> tuple[str, str | None]:
    """Busca CPF na mensagem. Retorna (mensagem_censurada, cpf_formatado)."""
    cpf_pattern = r"\b(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})\b"
    match = re.search(cpf_pattern, text)
    if match:
        full_cpf = "".join(match.groups())
        formatted = _format_cpf(full_cpf)
        censored = f"{full_cpf[:3]}.{full_cpf[3:5]}*.***-**"
        censored_text = re.sub(cpf_pattern, censored, text)
        return censored_text, formatted

    pure_pattern = r"\b\d{11}\b"
    pure_match = re.search(pure_pattern, text)
    if pure_match:
        full_cpf = pure_match.group(0)
        formatted = _format_cpf(full_cpf)
        censored = f"{full_cpf[:3]}.{full_cpf[3:5]}*.***-**"
        censored_text = re.sub(pure_pattern, censored, text)
        return censored_text, formatted

    return text, None
