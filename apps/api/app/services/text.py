import re


def normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^\w\s가-힣áéíóúñü]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()
