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

    monkeypatch.setattr(sessions_module.content_agent, "_gemini_generate", _raise_gemini_error)

    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200
    data = start.json()
    # Template fallback includes this phrase in the deterministic response body.
    assert "Grounded curriculum notes" in data["explanation"]
