from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.core.settings import settings


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)


def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()
