import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.model_registry import PolicyViolation, resolve_role
from app.core.reasoning import ReasoningEngine
from app.core.query_optimizer import QueryOptimizer
from app.memory.episodic import MemorySkeletonizer
from app.skills.manager import SkillManager


def test_model_role_governance_enforces_local_verifier(monkeypatch, tmp_path):
    registry = {
        "models": {
            "local-verifier": {"id": "phi4", "provider": "ollama", "cost_per_1k": 0.0},
            "cloud": {"id": "gemini-2.5-flash", "provider": "gemini", "cost_per_1k": 0.1},
        },
        "roles": {
            "verifier": "cloud",
            "optimizer": "cloud",
        },
        "settings": {"enforce_local_verifier": True},
    }
    path = tmp_path / "models_registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")

    from app.core import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "model_registry_file", str(path))
    monkeypatch.setattr(settings_mod.settings, "enforce_local_verifier", True)

    with pytest.raises(PolicyViolation):
        resolve_role("verifier")


def test_reasoning_loop_tracks_states_and_refines(monkeypatch):
    class FakeVerifier:
        def __init__(self):
            self.count = 0

        async def verify(self, query, draft, context=""):
            self.count += 1
            if self.count == 1:
                return 60, "too weak"
            return 92, "good"

    class FakeGenerator:
        async def generate(self, prompt: str):
            return "refined draft", {"provider": "fake"}

    async def _run():
        r = ReasoningEngine()
        r.verifier = FakeVerifier()
        r.generator = FakeGenerator()

        async def _gen():
            return "initial draft"

        draft, history = await r.run_loop(query="q", generate_func=_gen, context="ctx", max_refinements=2)
        assert draft == "refined draft"
        states = [h.get("state") for h in history]
        assert "verified" in states
        assert "refined" in states
        assert "accepted" in states

    asyncio.run(_run())


def test_query_optimizer_fallback_on_parse_failure(monkeypatch):
    class FakeProvider:
        async def generate(self, prompt: str):
            return "not-json", {"provider": "fake"}

    async def _run():
        opt = QueryOptimizer()
        opt.provider = FakeProvider()
        out = await opt.optimize_query("fix bug")
        assert out["optimized"] == "fix bug"
        assert out["reasoning"] in {"optimized", "invalid_optimizer_json", "No optimization output", "optimizer_failed"}

    asyncio.run(_run())


def test_markdown_skill_loading_and_injection(tmp_path):
    skills_root = tmp_path / "skills"
    lib = skills_root / "library"
    skill_dir = lib / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---\nname: demo-skill\nversion: 1.0.0\ndescription: Demo\nintent_triggers: [\"demo action\"]\n---\n\n# Demo\nUse safe tools only.\n""",
        encoding="utf-8",
    )

    sm = SkillManager()
    sm.skills_dir = lib
    sm.registry_file = lib / "registry.json"
    sm._ensure_paths()
    reg = sm.scan_and_register()
    assert "demo-skill" in reg
    assert sm.match_intent("please run demo action now") == "demo-skill"

    skill = sm.get_skill("demo-skill")
    assert skill is not None

    async def _run():
        out = await skill.on_run_start("base prompt")
        assert "Active Skill: demo-skill" in out
        assert "Use safe tools only." in out

    asyncio.run(_run())


def test_memory_skeletonizer_preserves_logic_and_actions():
    payload = {
        "run_id": "r1",
        "query": "q",
        "status": "completed",
        "updated_at": "2026-03-03T00:00:00+00:00",
        "nodes": [
            {
                "id": "n1",
                "agent": "PlannerAgent",
                "description": "d",
                "status": "completed",
                "agent_prompt": "plan this",
                "output": {"reasoning": "because", "_reasoning_trace": [{"score": 80}]},
                "iterations": [{"output": {"call_tool": {"name": "search", "arguments": {"q": "x"}}}}],
            }
        ],
        "edges": [{"source": "n1", "target": "n2"}],
    }
    sk = MemorySkeletonizer.skeletonize(payload)
    assert sk["run_id"] == "r1"
    assert sk["nodes"][0]["logic_prompt"] == "plan this"
    assert "logic" in sk["nodes"][0]
    assert sk["nodes"][0]["actions"][0]["type"] == "tool"
