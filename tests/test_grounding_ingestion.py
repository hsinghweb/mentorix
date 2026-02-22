"""Tests for grounding ingestion: PDF/text parse integrity, embedding dimensions, ingestion idempotency."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "API"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("EMBEDDING_PROVIDER", "local")

from app.core.settings import settings
from app.rag.embeddings import embed_text
from app.rag.grounding_ingest import (
    GroundingDoc,
    _hash_text,
    _read_document_text,
    _split_chunks,
    run_grounding_ingestion,
)


# ---- PDF / text parse integrity ----


def test_read_document_text_txt_roundtrip(tmp_path):
    """Reading a .txt file returns its content unchanged (parse integrity)."""
    content = "Chapter 1. Real Numbers.\n1.1 Introduction to real numbers."
    path = tmp_path / "syllabus.txt"
    path.write_text(content, encoding="utf-8")
    assert _read_document_text(path) == content


def test_read_document_text_txt_preferred_over_pdf(tmp_path):
    """When both .txt and .pdf exist, .txt is used (sibling with same stem)."""
    txt_content = "Text version content."
    path_pdf = tmp_path / "doc.pdf"
    path_txt = tmp_path / "doc.txt"
    path_txt.write_text(txt_content, encoding="utf-8")
    path_pdf.write_bytes(b"dummy pdf")
    # _read_document_text for .pdf checks path.with_suffix(".txt") first
    assert _read_document_text(path_pdf) == txt_content


def test_split_chunks_deterministic():
    """Same input and settings produce same chunks (parse integrity)."""
    text = "A" * 2000 + " B " + "C" * 500
    size, overlap = 500, 50
    one = _split_chunks(text, size, overlap)
    two = _split_chunks(text, size, overlap)
    assert one == two
    assert len(one) >= 1
    assert all(len(c) <= size + 200 for c in one)


def test_hash_text_deterministic():
    """Hash of same content is deterministic."""
    text = "Same content here."
    assert _hash_text(text) == _hash_text(text)


# ---- Embedding dimension consistency ----


def test_embed_text_returns_correct_dimension():
    """embed_text returns a vector of length embedding_dimensions (local fallback)."""
    vec = embed_text("hello world")
    assert isinstance(vec, list)
    assert len(vec) == settings.embedding_dimensions
    assert all(isinstance(x, float) for x in vec)


def test_embed_text_empty_string_returns_correct_dimension():
    """Empty or whitespace-only text still returns correct dimension (zero vector)."""
    vec = embed_text("")
    assert len(vec) == settings.embedding_dimensions
    vec2 = embed_text("   ")
    assert len(vec2) == settings.embedding_dimensions


# ---- Ingestion idempotency ----


@pytest.mark.asyncio
async def test_ingestion_idempotency_same_content_skips_reembed(monkeypatch, tmp_path):
    """Running ingestion twice with same document content does not duplicate chunks (idempotent)."""
    from app.memory.database import SessionLocal

    doc_content = "Chapter 1. Real Numbers. Section 1.1. Rational numbers."
    doc_path = tmp_path / "ch_1.txt"
    doc_path.write_text(doc_content, encoding="utf-8")

    def mock_get_docs():
        return [
            GroundingDoc(
                path=doc_path,
                doc_type="chapter",
                title="Test Chapter 1",
                chapter_number=1,
            )
        ]

    monkeypatch.setattr("app.rag.grounding_ingest.get_required_grounding_docs", mock_get_docs)

    async with SessionLocal() as db:
        run1 = await run_grounding_ingestion(db, force_rebuild=True)
        run2 = await run_grounding_ingestion(db, force_rebuild=False)

    assert run1["status"] == "completed"
    assert run1["chunks"] >= 1
    # Second run: idempotent — same chunk count (no duplicate chunks)
    assert run2["status"] == "completed"
    assert run2["chunks"] == run1["chunks"]
