from abc import ABC, abstractmethod

from sqlalchemy import Select

from app.core.settings import settings
from app.models.entities import ConceptChunk


class VectorBackend(ABC):
    name: str

    @abstractmethod
    def order_concept_chunks(self, stmt: Select, query_vec: list[float]) -> Select:
        raise NotImplementedError


class PGVectorBackend(VectorBackend):
    name = "pgvector"

    def order_concept_chunks(self, stmt: Select, query_vec: list[float]) -> Select:
        return stmt.order_by(ConceptChunk.embedding.cosine_distance(query_vec))


class FaissBackend(VectorBackend):
    name = "faiss"

    def order_concept_chunks(self, stmt: Select, query_vec: list[float]) -> Select:
        # Scaffold only: retrieval remains SQL-based until a FAISS index service is introduced.
        raise NotImplementedError("FAISS backend scaffold is present but not yet wired.")


class ChromaBackend(VectorBackend):
    name = "chroma"

    def order_concept_chunks(self, stmt: Select, query_vec: list[float]) -> Select:
        # Scaffold only: retrieval remains SQL-based until a Chroma service is introduced.
        raise NotImplementedError("Chroma backend scaffold is present but not yet wired.")


def get_vector_backend() -> VectorBackend:
    backend = (settings.vector_backend or "").lower()
    if backend == "faiss":
        return FaissBackend()
    if backend == "chroma":
        return ChromaBackend()
    return PGVectorBackend()
