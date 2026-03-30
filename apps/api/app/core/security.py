import hashlib
import re
import uuid


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or uuid.uuid4().hex[:8]


def sha256_hexdigest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
