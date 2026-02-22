import pytest

from app.agents.content import ContentGenerationAgent
from app.memory.database import SessionLocal
from app.rag.retriever import retrieve_concept_chunks_with_meta


@pytest.mark.asyncio
async def test_retrieval_confidence_contract_returns_bounded_score():
    async with SessionLocal() as db:
        result = await retrieve_concept_chunks_with_meta(db, concept="linear_equations", top_k=3)
    assert "chunks" in result
    assert "retrieval_confidence" in result
    assert 0.0 <= float(result["retrieval_confidence"]) <= 1.0
    assert isinstance(result.get("message", ""), str)


@pytest.mark.asyncio
async def test_grounding_guardrail_triggers_for_insufficient_grounded_context():
    agent = ContentGenerationAgent()
    payload = {
        "concept": "quadratic_equations",
        "difficulty": 2,
        "retrieved_chunks": [
            "Learner memory context: User prefers structured examples and short explanations.",
            "Learner memory context: Learner profile indicates medium pace.",
        ],
        "profile_snapshot": {"concept_mastery": 0.2},
    }
    response = await agent.run(payload)
    assert response["grounding_status"] == "insufficient_context"
    assert response["citations"] == []
    assert "could not find enough grounded curriculum context" in response["explanation"].lower()

