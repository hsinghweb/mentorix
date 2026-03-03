import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.orchestrator.agent_compliance import AgentRole, AgentCoordinator


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _StubRunAgent:
    async def run(self, payload: dict):
        return {"ok": True, "payload": payload}


class _StubEvalAgent:
    async def evaluate(self, answer: str, expected_answer: str):
        return {"match": answer == expected_answer}


@pytest.mark.anyio
async def test_session17_dispatch_run_capability():
    c = AgentCoordinator()
    c.register(
        name="StubRun",
        role=AgentRole.EXECUTOR,
        capabilities={"do_work": "run"},
        handler=_StubRunAgent(),
    )

    out = await c.dispatch(
        run_id="r1",
        sender_role=AgentRole.PLANNER,
        target_agent="StubRun",
        capability="do_work",
        payload={"x": 1},
    )
    assert out["ok"] is True
    assert out["payload"]["x"] == 1


@pytest.mark.anyio
async def test_session17_dispatch_evaluate_capability():
    c = AgentCoordinator()
    c.register(
        name="StubEval",
        role=AgentRole.EVALUATOR,
        capabilities={"evaluate_answer": "evaluate"},
        handler=_StubEvalAgent(),
    )

    out = await c.dispatch(
        run_id="r2",
        sender_role=AgentRole.EXECUTOR,
        target_agent="StubEval",
        capability="evaluate_answer",
        payload={"answer": "42", "expected_answer": "42"},
    )
    assert out["match"] is True


@pytest.mark.anyio
async def test_session17_rejects_unregistered_capability():
    c = AgentCoordinator()
    c.register(
        name="StubRun",
        role=AgentRole.EXECUTOR,
        capabilities={"do_work": "run"},
        handler=_StubRunAgent(),
    )

    with pytest.raises(ValueError):
        await c.dispatch(
            run_id="r3",
            sender_role=AgentRole.PLANNER,
            target_agent="StubRun",
            capability="not_allowed",
            payload={},
        )
