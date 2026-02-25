import hashlib
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import DOMAIN_RAG, get_domain_logger
from app.core.settings import settings
from app.models.entities import CurriculumDocument, EmbeddingChunk, IngestionRun, SyllabusHierarchy
from app.rag.embeddings import embed_text

logger = get_domain_logger(__name__, DOMAIN_RAG)


@dataclass
class GroundingDoc:
    path: Path
    doc_type: str
    title: str
    chapter_number: int | None = None


def _workspace_root() -> Path:
    """Root for grounding data: env GROUNDING_WORKSPACE_ROOT if set, else repo root (parents[3] from API/app/rag/)."""
    if getattr(settings, "grounding_workspace_root", None) and str(settings.grounding_workspace_root).strip():
        return Path(settings.grounding_workspace_root.strip()).resolve()
    return Path(__file__).resolve().parents[3]


def _hash_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _extract_chapter_num(path: Path) -> int | None:
    match = re.search(r"ch[_\-\s]?(\d+)", path.stem.lower())
    if not match:
        return None
    return int(match.group(1))


def _parse_syllabus_hierarchy(
    raw_text: str, doc_type: str, doc_chapter_number: int | None
) -> list[dict]:
    """Parse chapter > section > concept from document text. Returns list of dicts with type, title, sort_order, chapter_number."""
    items: list[dict] = []
    lines = (raw_text or "").splitlines()
    sort_order = 0

    # For a chapter doc we may have a single chapter (doc_chapter_number) and sections/concepts inside.
    current_chapter_num = doc_chapter_number

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Chapter: "Chapter 1", "CHAPTER 1", "Ch. 1", or "1. Title"
        chapter_match = re.match(r"(?i)^(?:chapter|ch\.?)\s*(\d+)\s*[.:\-]?\s*(.*)$", line)
        if chapter_match:
            current_chapter_num = int(chapter_match.group(1))
            title = (chapter_match.group(2) or f"Chapter {current_chapter_num}").strip() or f"Chapter {current_chapter_num}"
            items.append({"type": "chapter", "title": title, "sort_order": sort_order, "chapter_number": current_chapter_num})
            sort_order += 1
            continue

        num_dot_title = re.match(r"^\s*(\d+)\s*[.:]\s+(.+)$", line)
        if num_dot_title and not re.match(r"^\d+\.\d+", line):
            # "1. Introduction" style chapter
            n = int(num_dot_title.group(1))
            if 1 <= n <= 15 and (current_chapter_num is None or n == current_chapter_num):
                current_chapter_num = n
                title = num_dot_title.group(2).strip()
                items.append({"type": "chapter", "title": title or f"Chapter {n}", "sort_order": sort_order, "chapter_number": n})
                sort_order += 1
            continue

        # Section: "1.1", "1.1 Real Numbers", "Section 1.1"
        section_match = re.match(r"(?i)^(?:section\s+)?(\d+)\.(\d+)\s*[.:\-]?\s*(.*)$", line)
        if section_match:
            ch_num = int(section_match.group(1))
            title = (section_match.group(3) or f"{section_match.group(1)}.{section_match.group(2)}").strip()
            items.append({"type": "section", "title": title, "sort_order": sort_order, "chapter_number": ch_num})
            sort_order += 1
            continue

        # Concept: "Concept:", "• concept name"
        if line.lower().startswith("concept:") or re.match(r"^[•\-]\s+", line):
            title = re.sub(r"^(?i)concept:\s*", "", line).strip()
            title = re.sub(r"^[•\-]\s+", "", title).strip()
            if title:
                items.append({"type": "concept", "title": title, "sort_order": sort_order, "chapter_number": current_chapter_num})
                sort_order += 1

    # If doc is a single chapter and we found no chapters but have doc_chapter_number, add one chapter node
    if doc_type == "chapter" and doc_chapter_number is not None and not any(i["type"] == "chapter" for i in items):
        items.insert(0, {"type": "chapter", "title": f"Chapter {doc_chapter_number}", "sort_order": 0, "chapter_number": doc_chapter_number})
        for i in items[1:]:
            i["sort_order"] = i["sort_order"] + 1

    return items


def _split_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if chunk_size <= 0:
        return [text]
    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - max(0, overlap))
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start += step
    return chunks


def _read_document_text(path: Path) -> str:
    txt_path = path.with_suffix(".txt")
    if txt_path.exists():
        return txt_path.read_text(encoding="utf-8", errors="ignore")

    if path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")

    if path.suffix.lower() == ".pdf":
        try:
            reader = PdfReader(str(path))
            text_parts: list[str] = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_parts.append(page_text)
            return "\n".join(text_parts)
        except Exception as exc:
            logger.warning("Failed PDF extraction for %s: %s", path, exc)
            return ""
    return ""


def get_required_grounding_docs() -> list[GroundingDoc]:
    root = _workspace_root()
    base_dir = root / settings.grounding_data_dir

    syllabus_path = base_dir / settings.grounding_syllabus_relative_path
    docs: list[GroundingDoc] = [
        GroundingDoc(
            path=syllabus_path,
            doc_type="syllabus",
            title="CBSE Class 10 Maths Syllabus",
            chapter_number=None,
        )
    ]

    chapters_dir = base_dir / settings.grounding_chapters_dir
    chapter_files = sorted(chapters_dir.glob("ch_*.pdf"), key=lambda p: _extract_chapter_num(p) or 9999)
    selected = chapter_files[: max(0, settings.grounding_chapter_count)]
    for chapter_file in selected:
        chapter_num = _extract_chapter_num(chapter_file)
        docs.append(
            GroundingDoc(
                path=chapter_file,
                doc_type="chapter",
                title=f"Class 10 Maths Chapter {chapter_num}" if chapter_num else chapter_file.stem,
                chapter_number=chapter_num,
            )
        )
    return docs


async def ensure_grounding_ready(db: AsyncSession) -> tuple[bool, dict]:
    docs = get_required_grounding_docs()
    missing_paths: list[str] = []
    missing_embeddings: list[str] = []

    for doc in docs:
        if not doc.path.exists():
            missing_paths.append(str(doc.path))
            continue

        row = (
            await db.execute(select(CurriculumDocument).where(CurriculumDocument.source_path == str(doc.path)))
        ).scalar_one_or_none()
        if row is None:
            missing_embeddings.append(str(doc.path))
            continue

        chunk_count = int(
            (
                await db.execute(
                    select(func.count()).select_from(EmbeddingChunk).where(EmbeddingChunk.document_id == row.id)
                )
            ).scalar_one()
        )
        if chunk_count <= 0:
            missing_embeddings.append(str(doc.path))

    ready = not missing_paths and not missing_embeddings
    return ready, {"missing_paths": missing_paths, "missing_embeddings": missing_embeddings}


async def run_grounding_ingestion(db: AsyncSession, force_rebuild: bool = False) -> dict:
    docs = get_required_grounding_docs()
    logger.info("Grounding ingest started: force_rebuild=%s, documents=%d", force_rebuild, len(docs))
    ingestion_run = IngestionRun(status="started", total_documents=0, total_chunks=0, details={})
    db.add(ingestion_run)
    await db.flush()

    total_documents = 0
    total_chunks = 0
    details: dict[str, dict] = {}

    try:
        for doc in docs:
            doc_key = str(doc.path)
            logger.info("Processing document: %s (type=%s)", doc.path.name, doc.doc_type)
            if not doc.path.exists():
                logger.warning("Missing file: %s", doc_key)
                details[doc_key] = {"status": "missing_file"}
                continue

            raw_text = _read_document_text(doc.path)
            if not raw_text.strip():
                details[doc_key] = {"status": "empty_or_unreadable"}
                continue

            text_hash = _hash_text(raw_text)
            chunks = _split_chunks(raw_text, settings.grounding_chunk_size, settings.grounding_chunk_overlap)
            if not chunks:
                details[doc_key] = {"status": "no_chunks"}
                continue

            existing_doc = (
                await db.execute(select(CurriculumDocument).where(CurriculumDocument.source_path == str(doc.path)))
            ).scalar_one_or_none()
            if existing_doc is None:
                existing_doc = CurriculumDocument(
                    doc_type=doc.doc_type,
                    chapter_number=doc.chapter_number,
                    source_path=str(doc.path),
                    title=doc.title,
                    content_hash=text_hash,
                )
                db.add(existing_doc)
                await db.flush()
            elif force_rebuild or existing_doc.content_hash != text_hash:
                await db.execute(delete(EmbeddingChunk).where(EmbeddingChunk.document_id == existing_doc.id))
                existing_doc.content_hash = text_hash
                existing_doc.doc_type = doc.doc_type
                existing_doc.chapter_number = doc.chapter_number
                existing_doc.title = doc.title

            existing_chunk_count = int(
                (
                    await db.execute(
                        select(func.count()).select_from(EmbeddingChunk).where(EmbeddingChunk.document_id == existing_doc.id)
                    )
                ).scalar_one()
            )
            if existing_chunk_count > 0 and not force_rebuild and existing_doc.content_hash == text_hash:
                logger.info("Skipped unchanged: %s (%d chunks)", doc.path.name, existing_chunk_count)
                details[doc_key] = {"status": "skipped_unchanged", "chunks": existing_chunk_count}
                total_documents += 1
                total_chunks += existing_chunk_count
                continue

            logger.info("Embedding document: %s (%d chunks)", doc.path.name, len(chunks))
            await db.execute(delete(SyllabusHierarchy).where(SyllabusHierarchy.document_id == existing_doc.id))
            hierarchy_items = _parse_syllabus_hierarchy(raw_text, doc.doc_type, doc.chapter_number)
            last_chapter_id: uuid.UUID | None = None
            last_section_id: uuid.UUID | None = None
            for item in hierarchy_items:
                parent_id = None
                if item["type"] == "chapter":
                    last_chapter_id = uuid.uuid4()
                    last_section_id = None
                    db.add(
                        SyllabusHierarchy(
                            id=last_chapter_id,
                            document_id=existing_doc.id,
                            parent_id=None,
                            type="chapter",
                            title=item["title"][:512],
                            sort_order=item["sort_order"],
                            chapter_number=item.get("chapter_number"),
                        )
                    )
                    continue
                if item["type"] == "section":
                    last_section_id = uuid.uuid4()
                    parent_id = last_chapter_id
                    db.add(
                        SyllabusHierarchy(
                            id=last_section_id,
                            document_id=existing_doc.id,
                            parent_id=parent_id,
                            type="section",
                            title=item["title"][:512],
                            sort_order=item["sort_order"],
                            chapter_number=item.get("chapter_number"),
                        )
                    )
                    continue
                if item["type"] == "concept":
                    parent_id = last_section_id if last_section_id else last_chapter_id
                    db.add(
                        SyllabusHierarchy(
                            document_id=existing_doc.id,
                            parent_id=parent_id,
                            type="concept",
                            title=item["title"][:512],
                            sort_order=item["sort_order"],
                            chapter_number=item.get("chapter_number"),
                        )
                    )

            await db.execute(delete(EmbeddingChunk).where(EmbeddingChunk.document_id == existing_doc.id))
            for idx, chunk in enumerate(chunks):
                db.add(
                    EmbeddingChunk(
                        document_id=existing_doc.id,
                        doc_type=doc.doc_type,
                        chapter_number=doc.chapter_number,
                        chunk_index=idx,
                        content=chunk,
                        content_hash=_hash_text(chunk),
                        embedding=embed_text(chunk),
                    )
                )

            existing_doc.embedded_at = datetime.now(timezone.utc)
            total_documents += 1
            total_chunks += len(chunks)
            details[doc_key] = {"status": "embedded", "chunks": len(chunks)}

        ingestion_run.status = "completed"
        ingestion_run.total_documents = total_documents
        ingestion_run.total_chunks = total_chunks
        ingestion_run.details = details
        ingestion_run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info(
            "Grounding ingest completed: status=completed, documents=%d, chunks=%d",
            total_documents,
            total_chunks,
        )
    except Exception as exc:
        logger.exception("Grounding ingest failed: %s", exc)
        await db.rollback()
        ingestion_run.status = "failed"
        ingestion_run.details = details | {"error": "ingestion_failed"}
        ingestion_run.completed_at = datetime.now(timezone.utc)
        db.add(ingestion_run)
        await db.commit()
        raise

    return {
        "status": ingestion_run.status,
        "documents": total_documents,
        "chunks": total_chunks,
        "details": details,
    }
