"""
Integration tests for the learning flow — covers the full student lifecycle:
register → onboard → dashboard → read section → take test → advance week.

Run with: pytest tests/test_learning_flow.py -v
Requires: running API server at http://localhost:8000
"""
import pytest
import httpx
import asyncio
import sys
import time
import re
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

BASE = "http://localhost:8000"

# Test data
TEST_USER = {
    "username": "test_e2e_user_001",
    "password": "testpass123",
    "name": "E2E Test Student",
    "date_of_birth": "2010-06-15",
    "math_9_percent": 70,
    "selected_timeline_weeks": 14,
}


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE, timeout=60) as c:
        yield c


@pytest.fixture(scope="module")
def auth(client):
    """Register or login and return (token, learner_id)."""
    # Try login first
    resp = client.post("/auth/login", json={
        "username": TEST_USER["username"],
        "password": TEST_USER["password"],
    })
    if resp.status_code == 200:
        data = resp.json()
        return data["token"], data["learner_id"]

    # Register
    resp = client.post("/auth/signup", json=TEST_USER)
    assert resp.status_code in (200, 201), f"Registration failed: {resp.text}"
    data = resp.json()
    return data["token"], data["learner_id"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _normalize_q(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-zA-Z0-9]+", " ", str(text or "").lower())).strip()


def _create_fresh_user(client, prefix: str = "iter9") -> tuple[str, str]:
    ts = int(time.time() * 1000)
    user = {
        "username": f"{prefix}_{ts}",
        "password": "testpass123",
        "name": "Iteration9 Seed User",
        "date_of_birth": "2010-06-15",
        "math_9_percent": 62,
        "selected_timeline_weeks": 14,
    }
    signup = client.post("/auth/signup", json=user)
    assert signup.status_code in (200, 201), signup.text
    payload = signup.json()
    return payload["token"], payload["learner_id"]


def _seed_completed_chapter_progression(client, token: str, learner_id: str, chapter_number: int) -> None:
    """
    Deterministically mark all subsection progression rows completed for one chapter.
    Used only in tests to avoid nondeterministic skips when gating final tests.
    """
    dash = client.get(f"/learning/dashboard/{learner_id}", headers=_headers(token))
    assert dash.status_code == 200, dash.text
    week_tasks = dash.json().get("current_week_tasks", [])
    chapter_label = f"Chapter {chapter_number}"
    read_tasks = {
        t.get("section_id"): t.get("task_id")
        for t in week_tasks
        if t.get("chapter") == chapter_label and t.get("task_type") == "read" and t.get("section_id")
    }
    test_tasks = {
        t.get("section_id"): t.get("task_id")
        for t in week_tasks
        if t.get("chapter") == chapter_label and t.get("task_type") == "test" and t.get("section_id")
    }

    sec = client.get(f"/learning/chapter/{chapter_number}/sections/{learner_id}", headers=_headers(token))
    assert sec.status_code == 200, sec.text
    sections = sec.json().get("sections", [])
    assert sections, "Expected sections for chapter seeding."

    for section in sections:
        section_id = section["section_id"]
        # Load content (cache side-effects) and then complete reading task directly.
        read_load = client.post("/learning/content/section", json={
            "learner_id": learner_id,
            "chapter_number": chapter_number,
            "section_id": section_id,
            "regenerate": False,
        }, headers=_headers(token))
        assert read_load.status_code == 200, read_load.text

        task_id = read_tasks.get(section_id)
        if task_id:
            read_complete = client.post("/learning/reading/complete", json={
                "learner_id": learner_id,
                "task_id": task_id,
                "time_spent_seconds": 181,
            }, headers=_headers(token))
            assert read_complete.status_code == 200, read_complete.text

        gen = client.post("/learning/test/section/generate", json={
            "learner_id": learner_id,
            "chapter_number": chapter_number,
            "section_id": section_id,
            "regenerate": True,
        }, headers=_headers(token))
        assert gen.status_code == 200, gen.text
        test_data = gen.json()
        test_id = test_data["test_id"]
        questions = test_data.get("questions", [])
        assert questions

        # First submit yields question_results with correct indexes.
        probe_submit = client.post("/learning/test/submit", json={
            "learner_id": learner_id,
            "test_id": test_id,
            "answers": [{"question_id": q["question_id"], "selected_index": 0} for q in questions],
            "task_id": test_tasks.get(section_id),
        }, headers=_headers(token))
        assert probe_submit.status_code == 200, probe_submit.text
        probe_data = probe_submit.json()
        q_results = probe_data.get("question_results", [])
        assert q_results

        perfect_answers = []
        for qr in q_results:
            correct_idx = qr.get("correct_index", 0)
            if not isinstance(correct_idx, int):
                correct_idx = 0
            perfect_answers.append({
                "question_id": qr["question_id"],
                "selected_index": correct_idx,
            })

        # Second submit with exact answers should set subsection status completed.
        final_submit = client.post("/learning/test/submit", json={
            "learner_id": learner_id,
            "test_id": test_id,
            "answers": perfect_answers,
            "task_id": test_tasks.get(section_id),
        }, headers=_headers(token))
        assert final_submit.status_code == 200, final_submit.text

    # Verify chapter sections are now completed.
    check = client.get(f"/learning/chapter/{chapter_number}/sections/{learner_id}", headers=_headers(token))
    assert check.status_code == 200, check.text
    statuses = [s.get("status") for s in check.json().get("sections", [])]
    assert statuses and all(s == "completed" for s in statuses), f"Seeding failed: {statuses}"


class TestLearningFlow:
    """End-to-end learning flow tests."""

    def test_01_dashboard_loads(self, client, auth):
        token, learner_id = auth
        resp = client.get(f"/learning/dashboard/{learner_id}", headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "current_week" in data
        assert "chapter_status" in data
        assert "current_week_tasks" in data
        assert data["overall_mastery_percent"] >= 0

    def test_02_syllabus_available(self, client, auth):
        token, _ = auth
        resp = client.get("/learning/syllabus", headers=_headers(token))
        # Endpoint may or may not exist yet; if it does, check structure
        if resp.status_code == 200:
            data = resp.json()
            assert len(data) >= 14

    def test_03_section_content_generation(self, client, auth):
        token, learner_id = auth
        resp = client.post("/learning/content/section", json={
            "learner_id": learner_id,
            "chapter_number": 1,
            "section_id": "1.1",
        }, headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert data["source"] in ("llm", "cached", "rag_only", "fallback")

    def test_04_section_content_caching(self, client, auth):
        token, learner_id = auth
        # Request same section again — should come from cache
        resp = client.post("/learning/content/section", json={
            "learner_id": learner_id,
            "chapter_number": 1,
            "section_id": "1.1",
        }, headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "cached"

    def test_05_section_content_regenerate(self, client, auth):
        token, learner_id = auth
        resp = client.post("/learning/content/section", json={
            "learner_id": learner_id,
            "chapter_number": 1,
            "section_id": "1.1",
            "regenerate": True,
        }, headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] in ("llm", "rag_only", "fallback")

    def test_06_section_test_generation(self, client, auth):
        token, learner_id = auth
        resp = client.post("/learning/test/section/generate", json={
            "learner_id": learner_id,
            "chapter_number": 1,
            "section_id": "1.2",
        }, headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "test_id" in data
        assert "questions" in data
        assert len(data["questions"]) >= 3

    def test_07_chapter_sections_progress(self, client, auth):
        token, learner_id = auth
        resp = client.get(
            f"/learning/chapter/1/sections/{learner_id}",
            headers=_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sections" in data

    def test_07b_week_tasks_are_subsection_first(self, client, auth):
        token, learner_id = auth
        resp = client.get(f"/learning/dashboard/{learner_id}", headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        tasks = data.get("current_week_tasks", [])
        assert all("Practice worksheet" not in (t.get("title") or "") for t in tasks)
        # Legacy users may have old week tasks; validate subsection model via sections API.
        sec = client.get(f"/learning/chapter/1/sections/{learner_id}", headers=_headers(token))
        assert sec.status_code == 200, sec.text
        sec_data = sec.json()
        section_ids = {s.get("section_id") for s in sec_data.get("sections", [])}
        assert "1.1" in section_ids
        assert "1.4" in section_ids

    def test_07c_chapter_test_generation_cache(self, client, auth):
        token, learner_id = _create_fresh_user(client, "iter9_cache")
        chapter_number = 1
        _seed_completed_chapter_progression(client, token, learner_id, chapter_number)
        payload = {"learner_id": learner_id, "chapter_number": chapter_number, "regenerate": False}

        first = client.post("/learning/test/generate", json=payload, headers=_headers(token))
        assert first.status_code == 200, first.text
        first_data = first.json()
        assert not first_data.get("blocked", False)
        assert "test_id" in first_data
        assert "questions" in first_data
        assert first_data.get("source") in ("llm", "cached")

        second = client.post("/learning/test/generate", json=payload, headers=_headers(token))
        assert second.status_code == 200, second.text
        second_data = second.json()
        assert second_data.get("source") == "cached"
        assert second_data.get("test_id") == first_data.get("test_id")
        q_norm = [_normalize_q(q.get("prompt")) for q in second_data.get("questions", [])]
        assert len(q_norm) == len(set(q_norm)), "Expected unique chapter test question stems."

    def test_07ca_final_test_generation_blocked_before_prerequisites(self, client):
        # Fresh learner should have pending subsection tasks in current week.
        user = {
            "username": f"test_iter9_block_{int(time.time())}",
            "password": "testpass123",
            "name": "Iteration9 Blocked User",
            "date_of_birth": "2010-06-15",
            "math_9_percent": 55,
            "selected_timeline_weeks": 14,
        }
        signup = client.post("/auth/signup", json=user)
        assert signup.status_code in (200, 201), signup.text
        auth_data = signup.json()
        token = auth_data["token"]
        learner_id = auth_data["learner_id"]

        # Chapter 1 should be week-1 planned and blocked until subsection tasks complete.
        gen = client.post("/learning/test/generate", json={
            "learner_id": learner_id,
            "chapter_number": 1,
            "regenerate": False,
        }, headers=_headers(token))
        assert gen.status_code == 200, gen.text
        payload = gen.json()
        assert payload.get("blocked") is True
        assert payload.get("reason_code") == "pending_subsection_tasks"
        assert isinstance(payload.get("pending_tasks"), list) and payload.get("pending_tasks")
        assert payload.get("test_id") in (None, "")
        assert payload.get("questions") == []

    def test_07d_question_explain_cache(self, client, auth):
        token, learner_id = auth
        section_id = "1.2"
        chapter_number = 1
        gen = client.post("/learning/test/section/generate", json={
            "learner_id": learner_id,
            "chapter_number": chapter_number,
            "section_id": section_id,
            "regenerate": False,
        }, headers=_headers(token))
        assert gen.status_code == 200, gen.text
        gen_data = gen.json()
        test_id = gen_data["test_id"]
        questions = gen_data["questions"]
        assert questions
        q_norm = [_normalize_q(q.get("prompt")) for q in questions]
        assert len(q_norm) == len(set(q_norm)), "Expected unique section test question stems."

        explain_payload = {
            "learner_id": learner_id,
            "test_id": test_id,
            "question_id": questions[0]["question_id"],
            "selected_index": 0,
            "regenerate": False,
        }
        first = client.post("/learning/test/question/explain", json=explain_payload, headers=_headers(token))
        assert first.status_code == 200, first.text
        first_data = first.json()
        assert first_data.get("explanation")
        assert first_data.get("source") in ("llm", "cached", "fallback")

        second = client.post("/learning/test/question/explain", json=explain_payload, headers=_headers(token))
        assert second.status_code == 200, second.text
        second_data = second.json()
        assert second_data.get("source") == "cached"

    def test_07e_chapter_final_generate_submit_score(self, client, auth):
        token, learner_id = _create_fresh_user(client, "iter9_final")
        chapter_number = 1
        _seed_completed_chapter_progression(client, token, learner_id, chapter_number)
        gen = client.post("/learning/test/generate", json={
            "learner_id": learner_id,
            "chapter_number": chapter_number,
            "regenerate": True,
        }, headers=_headers(token))
        assert gen.status_code == 200, gen.text
        gen_data = gen.json()
        assert "test_id" in gen_data
        assert len(gen_data.get("questions", [])) >= 5

        q0 = gen_data["questions"][0]
        submit = client.post("/learning/test/submit", json={
            "learner_id": learner_id,
            "test_id": gen_data["test_id"],
            "answers": [{"question_id": q0["question_id"], "selected_index": 0}],
            "task_id": None,
        }, headers=_headers(token))
        assert submit.status_code == 200, submit.text
        result = submit.json()
        assert "score" in result
        assert "correct" in result
        assert "total" in result

    def test_08_plan_history(self, client, auth):
        token, learner_id = auth
        resp = client.get(f"/learning/plan-history/{learner_id}", headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "versions" in data
        assert isinstance(data["versions"], list)

    def test_08b_confidence_trend(self, client, auth):
        token, learner_id = auth
        resp = client.get(f"/learning/confidence-trend/{learner_id}", headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "points" in data
        assert "trend" in data

    def test_09_decision_history(self, client, auth):
        token, learner_id = auth
        resp = client.get(f"/learning/decisions/{learner_id}", headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "decisions" in data
        assert isinstance(data["decisions"], list)


class TestAgentUnits:
    """Unit tests for agent modules."""

    def test_planner_agent(self):
        from app.agents.planner import CurriculumPlannerAgent
        agent = CurriculumPlannerAgent()
        result = asyncio.run(agent.run({
            "mastery_map": {"Chapter 1": 0.8, "Chapter 2": 0.3, "Chapter 3": 0.0},
            "total_weeks": 14,
            "current_week": 1,
            "cognitive_depth": 0.5,
            "mode": "generate",
        }))
        assert "plan" in result
        assert result["remaining_chapters"] > 0

    def test_profiling_agent(self):
        from app.agents.learner_profile import LearnerProfilingAgent
        agent = LearnerProfilingAgent()
        result = asyncio.run(agent.run({
            "mastery_map": {"Chapter 1": 0.9, "Chapter 2": 0.1},
            "cognitive_depth": 0.6,
            "engagement_score": 0.7,
        }))
        assert "chapter_breakdown" in result
        assert "confidence_metric" in result
        assert "weak_zones" in result

    def test_revision_agent(self):
        from app.agents.progress_revision import ProgressRevisionAgent
        agent = ProgressRevisionAgent()
        result = asyncio.run(agent.run({
            "mastery_map": {"Chapter 1": 0.7, "Chapter 2": 0.3},
            "current_week": 5,
            "completed_chapters": ["Chapter 1", "Chapter 2"],
            "chapter_last_practiced": {"Chapter 1": 1, "Chapter 2": 2},
        }))
        assert "revision_recommendations" in result
        assert "average_retention" in result
