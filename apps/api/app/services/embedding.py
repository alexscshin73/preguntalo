import hashlib
import math
import re

import httpx

from app.core.config import EMBEDDING_DIMENSIONS, get_settings


class EmbeddingService:
    """Uses a local embedding endpoint when available and falls back to deterministic local embeddings."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.dimensions = EMBEDDING_DIMENSIONS
        self.model = self.settings.local_embedding_model
        self.base_url = self.settings.local_ai_base_url.rstrip("/")
        self.timeout = self.settings.local_ai_timeout_seconds

    def embed_texts(self, texts: list[str]) -> tuple[list[list[float]], str]:
        if not texts:
            return [], self.model

        remote_vectors = self._embed_with_local_model(texts)
        if remote_vectors is not None:
            return remote_vectors, self.model

        return [self._fallback_embedding(text) for text in texts], f"local-hash-{self.dimensions}"

    def embed_text(self, text: str) -> tuple[list[float], str]:
        vectors, model_name = self.embed_texts([text])
        return vectors[0], model_name

    def cosine_similarity(self, left: list[float] | None, right: list[float] | None) -> float:
        if left is None or right is None:
            return 0.0

        left_values = [float(value) for value in left]
        right_values = [float(value) for value in right]
        if len(left_values) == 0 or len(right_values) == 0:
            return 0.0

        numerator = sum(a * b for a, b in zip(left_values, right_values, strict=False))
        left_norm = math.sqrt(sum(value * value for value in left_values))
        right_norm = math.sqrt(sum(value * value for value in right_values))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _fallback_embedding(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[\w가-힣áéíóúñü]+", text.lower())
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0)
            vector[index] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]

    def _embed_with_local_model(self, texts: list[str]) -> list[list[float]] | None:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/embed",
                    json={
                        "model": self.model,
                        "input": texts,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except Exception:  # noqa: BLE001
            return None

        raw_embeddings = payload.get("embeddings")
        if isinstance(raw_embeddings, list) and raw_embeddings:
            return [self._resize_embedding(vector) for vector in raw_embeddings if isinstance(vector, list)]

        raw_embedding = payload.get("embedding")
        if isinstance(raw_embedding, list):
            return [self._resize_embedding(raw_embedding)]

        return None

    def _resize_embedding(self, vector: list[float]) -> list[float]:
        cleaned = [float(value) for value in vector]
        if len(cleaned) >= self.dimensions:
            resized = cleaned[: self.dimensions]
        else:
            resized = cleaned + [0.0] * (self.dimensions - len(cleaned))

        norm = math.sqrt(sum(value * value for value in resized))
        if norm == 0.0:
            return resized
        return [value / norm for value in resized]
