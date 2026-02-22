from __future__ import annotations

import uuid


def test_happy_path_session_submit_dashboard(client):
    learner_id = str(uuid.uuid4())

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json().get("status") == "ok"

    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200
    start_data = start.json()
    assert start_data["session_id"]
    assert start_data["concept"]
    assert start_data["difficulty"] in [1, 2, 3]
    assert isinstance(start_data["explanation"], str) and start_data["explanation"]
    assert isinstance(start_data["question"], str) and start_data["question"]

    submit = client.post(
        "/submit-answer",
        json={
            "session_id": start_data["session_id"],
            "answer": "I tried solving this concept with stepwise reasoning.",
            "response_time": 8.5,
        },
    )
    assert submit.status_code == 200
    submit_data = submit.json()
    assert 0.0 <= float(submit_data["score"]) <= 1.0
    assert submit_data["error_type"]
    assert isinstance(submit_data["next_explanation"], str)
    assert "adaptation_applied" in submit_data
    assert "new_difficulty" in submit_data["adaptation_applied"]

    dashboard = client.get(f"/dashboard/{learner_id}")
    assert dashboard.status_code == 200
    dashboard_data = dashboard.json()
    assert isinstance(dashboard_data.get("mastery_map"), dict)
    assert isinstance(dashboard_data.get("weak_areas"), list)
    assert isinstance(dashboard_data.get("last_sessions"), list)


def test_failure_missing_or_expired_session(client):
    missing_session_id = str(uuid.uuid4())
    response = client.post(
        "/submit-answer",
        json={
            "session_id": missing_session_id,
            "answer": "sample",
            "response_time": 5.0,
        },
    )
    assert response.status_code == 404
    body = response.json()
    assert "Session not found or expired" in str(body)


def test_grounding_status_endpoint_shape(client):
    response = client.get("/grounding/status")
    assert response.status_code == 200
    body = response.json()
    assert "ready" in body
    assert "missing_paths" in body
    assert "missing_embeddings" in body


def test_onboarding_start_endpoint_available(client):
    response = client.post(
        "/onboarding/start",
        json={"name": "Test Learner", "grade_level": "10", "exam_in_months": 10},
    )
    # When grounding isn't ingested yet, endpoint returns 400 by design.
    # Otherwise it returns generated diagnostic questions.
    assert response.status_code in (200, 400)
    body = response.json()
    if response.status_code == 200:
        assert "learner_id" in body
        assert "diagnostic_attempt_id" in body
        assert isinstance(body.get("questions"), list)
    else:
        assert "Run /grounding/ingest first" in str(body)


def test_weekly_replan_policy_flow(client):
    learner_id = str(uuid.uuid4())
    # Ensures learner/profile exists through existing stable MVP flow.
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200

    r1 = client.post(
        "/onboarding/weekly-replan",
        json={
            "learner_id": learner_id,
            "evaluation": {"chapter": "Chapter 1", "score": 0.40},
            "threshold": 0.60,
            "max_attempts": 3,
        },
    )
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["decision"] == "repeat_chapter"
    assert body1["attempt_count"] == 1

    r2 = client.post(
        "/onboarding/weekly-replan",
        json={
            "learner_id": learner_id,
            "evaluation": {"chapter": "Chapter 1", "score": 0.50},
            "threshold": 0.60,
            "max_attempts": 3,
        },
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["decision"] in ("proceed_with_revision_queue", "repeat_chapter")
    assert body2["attempt_count"] == 2


def test_onboarding_plan_endpoint_available(client):
    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200

    response = client.get(f"/onboarding/plan/{learner_id}")
    assert response.status_code in (200, 404)


def test_failure_embedding_service_unavailable_falls_back(client, monkeypatch):
    from app.rag import embeddings

    def _raise_embedding_error(*_args, **_kwargs):
        raise RuntimeError("embedding service unavailable")

    monkeypatch.setattr(embeddings.httpx, "post", _raise_embedding_error)

    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200
    data = start.json()
    assert data["session_id"]
    assert data["explanation"]


def test_failure_gemini_unavailable_uses_template_fallback(client, monkeypatch):
    from app.api import sessions as sessions_module

    async def _raise_gemini_error(_prompt: str):
        raise RuntimeError("gemini unavailable")

    async def _broken_generate(prompt: str):
        await _raise_gemini_error(prompt)

    monkeypatch.setattr(sessions_module.content_agent.provider, "generate", _broken_generate)

    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200
    data = start.json()
    # Template fallback includes this phrase in the deterministic response body.
    assert "Grounded curriculum notes" in data["explanation"]


def test_memory_status_endpoint_shape(client):
    response = client.get("/memory/status")
    assert response.status_code == 200
    body = response.json()
    assert "configured_backend" in body
    assert "active_mode" in body
    assert "dual_write_enabled" in body
    assert "mongo" in body
    assert "connected" in body["mongo"]


def test_memory_write_flow_for_active_backend(client):
    from app.memory.ingest import ingest_session_signal

    status = client.get("/memory/status")
    assert status.status_code == 200
    assert "active_mode" in status.json()

    learner_id = str(uuid.uuid4())
    ingest_session_signal(
        learner_id=learner_id,
        concept="linear_equations",
        score=0.7,
        adaptation_score=0.3,
    )

    memory_ctx = client.get(f"/memory/context/{learner_id}")
    assert memory_ctx.status_code == 200
    context = memory_ctx.json()["context"]
    assert isinstance(context, dict)
    assert any(bool(context.get(key)) for key in ("learner_preferences", "operating_context", "soft_identity"))
