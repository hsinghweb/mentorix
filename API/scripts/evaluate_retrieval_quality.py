from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.database import SessionLocal
from app.rag.retriever import retrieve_concept_chunks_with_meta


GOLDEN_CASES = [
    {"concept": "fractions", "must_contain": ["fraction", "whole"]},
    {"concept": "linear_equations", "must_contain": ["linear", "equation"]},
    {"concept": "quadratic_equations", "must_contain": ["quadratic", "equation"]},
]


def _contains_any(text: str, keywords: list[str]) -> bool:
    hay = (text or "").lower()
    return any(k.lower() in hay for k in keywords)


async def evaluate_case(db: AsyncSession, concept: str, must_contain: list[str]) -> dict:
    result = await retrieve_concept_chunks_with_meta(db=db, concept=concept, top_k=3)
    chunks = result.get("chunks", [])
    combined = "\n".join(chunks)
    keyword_match = _contains_any(combined, must_contain)
    return {
        "concept": concept,
        "retrieval_confidence": result.get("retrieval_confidence", 0.0),
        "candidate_count": result.get("candidate_count", 0),
        "semantic_fallback_used": result.get("semantic_fallback_used", False),
        "keyword_match": keyword_match,
        "pass": bool(chunks) and keyword_match,
        "message": result.get("message", ""),
    }


async def main_async() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality on local golden concepts.")
    parser.add_argument("--json", action="store_true", help="Print JSON output only.")
    args = parser.parse_args()

    reports = []
    async with SessionLocal() as db:
        for case in GOLDEN_CASES:
            reports.append(await evaluate_case(db, case["concept"], case["must_contain"]))

    summary = {
        "total": len(reports),
        "passed": sum(1 for r in reports if r["pass"]),
        "failed": sum(1 for r in reports if not r["pass"]),
        "avg_confidence": round(sum(float(r["retrieval_confidence"]) for r in reports) / max(1, len(reports)), 3),
        "reports": reports,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
        return

    print("Retrieval Evaluation Summary")
    print(f"Passed: {summary['passed']}/{summary['total']} | Avg confidence: {summary['avg_confidence']}")
    for r in reports:
        status = "PASS" if r["pass"] else "FAIL"
        print(
            f"- {status} {r['concept']}: confidence={r['retrieval_confidence']} "
            f"candidates={r['candidate_count']} fallback={r['semantic_fallback_used']}"
        )

    print("\nJSON report:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main_async())
