import json
from pathlib import Path

FAQ_PATH = Path("docs/faq.json")
_cache: list[dict] = []


def load_faq() -> list[dict]:
    global _cache
    if not _cache:
        with open(FAQ_PATH, encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache


def search_faq(message: str) -> tuple[str | None, float]:
    faq = load_faq()
    msg = message.lower()
    best, best_score = None, 0.0

    for entry in faq:
        keywords = [k.strip().lower() for k in entry["keywords"].split(",")]
        score = sum(1 for kw in keywords if kw in msg) / len(keywords)
        if score > best_score:
            best_score = score
            best = entry

    if best and best_score >= 0.5:
        return best["answer"], best_score
    return None, 0.0


def get_context(message: str, top: int = 3) -> str:
    faq = load_faq()
    msg = message.lower()
    scored = sorted(faq, key=lambda e: sum(
        1 for k in e["keywords"].split(",") if k.strip().lower() in msg
    ), reverse=True)

    relevant = scored[:top]
    if not relevant:
        return ""
    lines = ["FAQ disponível:"]
    for e in relevant:
        lines.append(f"P: {e['question']}\nR: {e['answer']}")
    return "\n\n".join(lines)