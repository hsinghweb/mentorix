"""
Integration tests for the learning flow — covers the full student lifecycle:
register → onboard → dashboard → read section → take test → advance week.

Run with: pytest tests/test_learning_flow.py -v
Requires: running API server at http://localhost:8000
"""
import pytest
import httpx

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
    resp = client.post("/auth/register", json=TEST_USER)
    assert resp.status_code in (200, 201), f"Registration failed: {resp.text}"
    data = resp.json()
    return data["token"], data["learner_id"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


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
            f"/learning/sections/1?learner_id={learner_id}",
            headers=_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sections" in data

    def test_08_plan_history(self, client, auth):
        token, learner_id = auth
        resp = client.get(f"/learning/plan/history/{learner_id}", headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "versions" in data
        assert isinstance(data["versions"], list)

    def test_09_decision_history(self, client, auth):
        token, learner_id = auth
        resp = client.get(f"/learning/decisions/{learner_id}", headers=_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "decisions" in data
        assert isinstance(data["decisions"], list)


class TestAgentUnits:
    """Unit tests for agent modules."""

    @pytest.mark.asyncio
    async def test_planner_agent(self):
        from app.agents.planner import CurriculumPlannerAgent
        agent = CurriculumPlannerAgent()
        result = await agent.run({
            "mastery_map": {"Chapter 1": 0.8, "Chapter 2": 0.3, "Chapter 3": 0.0},
            "total_weeks": 14,
            "current_week": 1,
            "cognitive_depth": 0.5,
            "mode": "generate",
        })
        assert "plan" in result
        assert result["remaining_chapters"] > 0

    @pytest.mark.asyncio
    async def test_profiling_agent(self):
        from app.agents.learner_profile import LearnerProfilingAgent
        agent = LearnerProfilingAgent()
        result = await agent.run({
            "mastery_map": {"Chapter 1": 0.9, "Chapter 2": 0.1},
            "cognitive_depth": 0.6,
            "engagement_score": 0.7,
        })
        assert "chapter_breakdown" in result
        assert "confidence_metric" in result
        assert "weak_zones" in result

    @pytest.mark.asyncio
    async def test_revision_agent(self):
        from app.agents.progress_revision import ProgressRevisionAgent
        agent = ProgressRevisionAgent()
        result = await agent.run({
            "mastery_map": {"Chapter 1": 0.7, "Chapter 2": 0.3},
            "current_week": 5,
            "completed_chapters": ["Chapter 1", "Chapter 2"],
            "chapter_last_practiced": {"Chapter 1": 1, "Chapter 2": 2},
        })
        assert "revision_recommendations" in result
        assert "average_retention" in result
