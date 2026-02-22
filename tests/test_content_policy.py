from __future__ import annotations

import pytest

from app.agents.content import ContentGenerationAgent


@pytest.mark.asyncio
async def test_content_guardrail_when_grounding_missing():
    agent = ContentGenerationAgent()
    out = await agent.run(
        {
            "concept": "linear_equations",
            "difficulty": 1,
            "retrieved_chunks": [],
            "profile_snapshot": {"concept_mastery": {"linear_equations": 0.4}},
        }
    )
    assert out["grounding_status"] == "insufficient_context"
    assert out["source"] == "grounding_guardrail"
    assert "could not find enough grounded curriculum context" in out["explanation"].lower()


@pytest.mark.asyncio
async def test_content_policy_adapts_examples_by_profile_band():
    agent = ContentGenerationAgent()
    weak = await agent.run(
        {
            "concept": "linear_equations",
            "difficulty": 1,
            "retrieved_chunks": ["Linear equations are solved by isolating the variable."],
            "profile_snapshot": {"concept_mastery": {"linear_equations": 0.3}},
        }
    )
    strong = await agent.run(
        {
            "concept": "linear_equations",
            "difficulty": 2,
            "retrieved_chunks": ["Linear equations are solved by isolating the variable."],
            "profile_snapshot": {"concept_mastery": {"linear_equations": 0.85}},
        }
    )
    assert weak["adaptation_policy"]["tone"] == "simple_supportive"
    assert strong["adaptation_policy"]["tone"] == "concise_challenging"
    assert len(weak["examples"]) > len(strong["examples"])
    assert weak["grounding_status"] == "grounded"
    assert strong["grounding_status"] == "grounded"
