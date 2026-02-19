import hashlib
import logging
import math
import re

import httpx

from app.core.settings import settings


EMBEDDING_DIM = 384
logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_]+", (text or "").lower())


def embed_text(text: str) -> list[float]:
    """
    Primary path: local Ollama nomic embeddings.
    Fallback path: deterministic CPU hashing (no external dependency).
    """
    if settings.embedding_provider.lower() == "ollama":
        try:
            response = httpx.post(
                f"{settings.ollama_base_url.rstrip('/')}/api/embeddings",
                json={"model": settings.embedding_model, "prompt": text},
                timeout=15.0,
            )
            response.raise_for_status()
            payload = response.json()
            emb = payload.get("embedding")
            if isinstance(emb, list) and emb:
                return [float(x) for x in emb]
        except Exception as exc:
            logger.warning("Ollama embedding failed, using deterministic fallback: %s", exc)

    vec = [0.0] * EMBEDDING_DIM
    tokens = _tokenize(text)
    if not tokens:
        return vec

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % EMBEDDING_DIM
        sign = 1.0 if (digest[4] % 2 == 0) else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec
