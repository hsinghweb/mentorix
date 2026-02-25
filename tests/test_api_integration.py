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


def test_student_learning_metrics_endpoint_contract(client):
    """GET /onboarding/learning-metrics/{learner_id} returns aggregated metrics shape."""
    learner_id = str(uuid.uuid4())
    client.post("/start-session", json={"learner_id": learner_id})
    client.get(f"/onboarding/tasks/{learner_id}")
    resp = client.get(f"/onboarding/learning-metrics/{learner_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["learner_id"] == learner_id
    assert "mastery_progression" in body
    assert "avg_mastery_score" in body
    assert "confidence_score" in body
    assert "weak_area_count" in body
    assert "weak_areas" in body
    assert "adherence_rate_week" in body
    assert "login_streak_days" in body
    assert "timeline_adherence_weeks" in body
    assert "forecast_drift_weeks" in body
    assert "selected_timeline_weeks" in body
    assert "current_forecast_weeks" in body
    assert "chapter_retry_counts" in body
    assert isinstance(body["chapter_retry_counts"], dict)
    assert 0 <= body["confidence_score"] <= 1
    assert body["login_streak_days"] >= 0


def test_forecast_history_endpoint_contract(client):
    """GET /onboarding/forecast-history/{learner_id} returns history list."""
    learner_id = str(uuid.uuid4())
    client.post("/start-session", json={"learner_id": learner_id})
    resp = client.get(f"/onboarding/forecast-history/{learner_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["learner_id"] == learner_id
    assert "history" in body
    assert isinstance(body["history"], list)


def test_app_metrics_endpoint_contract(client):
    response = client.get("/metrics/app")
    assert response.status_code == 200
    body = response.json()
    assert "request_count" in body
    assert "error_count" in body
    assert "error_rate" in body
    assert "latency_ms_p50" in body
    assert "latency_ms_p95" in body
    assert "alerts" in body
    assert isinstance(body["alerts"], list)
    assert 0 <= body["error_rate"] <= 1
    # Optional: agent/fleet summary (total_steps, failed_steps, step_success_rate, etc.)
    if body.get("agents") is not None:
        agents = body["agents"]
        assert "total_steps" in agents
        assert "failed_steps" in agents
        assert "step_success_rate" in agents
    # Cache (Redis) hit/miss metrics
    assert "cache" in body
    cache = body["cache"]
    assert "cache_hits" in cache
    assert "cache_misses" in cache
    assert "cache_sets" in cache
    assert "cache_get_total" in cache
    assert "cache_hit_ratio" in cache
    # RAG retrieval quality (relevance proxy)
    assert "retrieval" in body
    retrieval = body["retrieval"]
    assert "retrieval_count" in retrieval
    assert "retrieval_avg_confidence" in retrieval
    assert "retrieval_low_confidence_count" in retrieval
    assert "retrieval_low_confidence_ratio" in retrieval
    # Engagement / disengagement (extended alerts)
    assert "engagement" in body
    engagement = body["engagement"]
    assert "disengagement_recent_count" in engagement
    assert "disengagement_total_count" in engagement
    # DB query performance (p50/p95)
    assert "db" in body
    db = body["db"]
    assert "db_query_count" in db
    assert "db_p50_ms" in db
    assert "db_p95_ms" in db


def test_onboarding_start_endpoint_available(client):
    response = client.post(
        "/onboarding/start",
        json={
            "name": "Test Learner",
            "grade_level": "10",
            "exam_in_months": 10,
            "selected_timeline_weeks": 16,
        },
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


def test_onboarding_timeline_bounds_validation(client):
    response = client.post(
        "/onboarding/start",
        json={
            "name": "Bounds Learner",
            "grade_level": "10",
            "exam_in_months": 10,
            "selected_timeline_weeks": 10,
        },
    )
    assert response.status_code == 422


def test_onboarding_diagnostic_to_profile_timeline_integration(client, monkeypatch):
    """Full onboarding start -> submit; assert timeline bounds and recommendation payload."""
    from app.api import onboarding as onboarding_module

    # One chunk: content chosen so _extract_keywords last word is "clear" for fill_blank
    class MockChunk:
        content = "Something good and clear."
        chapter_number = 1

    async def _mock_get_diagnostic_chunks(_db):
        return [MockChunk()]

    monkeypatch.setattr(onboarding_module, "_get_diagnostic_chunks", _mock_get_diagnostic_chunks)

    start = client.post(
        "/onboarding/start",
        json={
            "name": "Finish Line Learner",
            "grade_level": "10",
            "exam_in_months": 10,
            "selected_timeline_weeks": 16,
        },
    )
    assert start.status_code == 200, start.text
    start_data = start.json()
    learner_id = start_data["learner_id"]
    diagnostic_attempt_id = start_data["diagnostic_attempt_id"]
    questions = start_data.get("questions", [])

    answers = []
    for q in questions:
        qid, qtype = q["question_id"], q.get("question_type", "")
        if qtype == "true_false":
            answers.append({"question_id": qid, "answer": "true"})
        elif qtype == "fill_blank":
            answers.append({"question_id": qid, "answer": "clear"})
        elif qtype == "mcq":
            answers.append({"question_id": qid, "answer": "1"})

    submit = client.post(
        "/onboarding/submit",
        json={
            "learner_id": learner_id,
            "diagnostic_attempt_id": diagnostic_attempt_id,
            "answers": answers,
            "time_spent_minutes": 15,
        },
    )
    assert submit.status_code == 200, submit.text
    body = submit.json()

    assert "recommended_timeline_weeks" in body
    assert "current_forecast_weeks" in body
    assert "timeline_delta_weeks" in body
    assert "timeline_recommendation_note" in body
    assert "selected_timeline_weeks" in body

    rec = int(body["recommended_timeline_weeks"])
    curr = int(body["current_forecast_weeks"])
    delta = int(body["timeline_delta_weeks"])
    assert 14 <= rec <= 28
    assert 14 <= curr <= 28
    assert curr - body["selected_timeline_weeks"] == delta
    assert isinstance(body["timeline_recommendation_note"], str) and len(body["timeline_recommendation_note"]) > 0
    assert isinstance(body.get("rough_plan"), list)
    assert isinstance(body.get("profile_snapshot"), dict)
    assert body["profile_snapshot"].get("current_forecast_weeks") == curr


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
    response = client.get(f"/onboarding/plan/{learner_id}")
    assert response.status_code == 404


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


def test_locked_task_completion_policy_flow(client):
    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200

    tasks_resp = client.get(f"/onboarding/tasks/{learner_id}")
    assert tasks_resp.status_code == 200
    tasks = tasks_resp.json().get("tasks", [])
    assert tasks
    read_task = tasks[0]
    assert read_task["is_locked"] is True
    assert read_task["status"] == "pending"

    fail_complete = client.post(
        f"/onboarding/tasks/{read_task['task_id']}/complete",
        json={"learner_id": learner_id, "reading_minutes": 1},
    )
    assert fail_complete.status_code == 200
    fail_body = fail_complete.json()
    assert fail_body["accepted"] is False
    assert fail_body["status"] == "pending"

    pass_complete = client.post(
        f"/onboarding/tasks/{read_task['task_id']}/complete",
        json={"learner_id": learner_id, "reading_minutes": 15},
    )
    assert pass_complete.status_code == 200
    pass_body = pass_complete.json()
    assert pass_body["accepted"] is True
    assert pass_body["status"] == "completed"


def test_revision_queue_trigger_flow(client):
    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200

    for score in (0.30, 0.35, 0.40):
        r = client.post(
            "/onboarding/weekly-replan",
            json={
                "learner_id": learner_id,
                "evaluation": {"chapter": "Chapter 2", "score": score},
                "threshold": 0.60,
                "max_attempts": 3,
            },
        )
        assert r.status_code == 200

    queue_resp = client.get(f"/onboarding/revision-queue/{learner_id}")
    assert queue_resp.status_code == 200
    items = queue_resp.json().get("items", [])
    assert any(item.get("chapter") == "Chapter 2" for item in items)


def test_no_skip_policy_override_checks(client):
    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200

    blocked = client.post(
        "/onboarding/chapters/advance",
        json={
            "learner_id": learner_id,
            "chapter": "Chapter 3",
            "score": 0.25,
            "threshold": 0.60,
            "allow_policy_override": False,
        },
    )
    assert blocked.status_code == 409

    allowed = client.post(
        "/onboarding/chapters/advance",
        json={
            "learner_id": learner_id,
            "chapter": "Chapter 3",
            "score": 0.25,
            "threshold": 0.60,
            "allow_policy_override": True,
            "override_reason": "Teacher approved controlled skip for pacing.",
        },
    )
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["advanced"] is True
    assert body["used_policy_override"] is True

    queue_resp = client.get(f"/onboarding/revision-queue/{learner_id}")
    assert queue_resp.status_code == 200
    items = queue_resp.json().get("items", [])
    assert any(item.get("chapter") == "Chapter 3" for item in items)


def test_weekly_plan_contract_and_versions(client):
    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200

    tasks_resp = client.get(f"/onboarding/tasks/{learner_id}")
    assert tasks_resp.status_code == 200

    plan_resp = client.get(f"/onboarding/plan/{learner_id}")
    assert plan_resp.status_code == 200
    plan_body = plan_resp.json()
    assert "committed_week_schedule" in plan_body
    assert "forecast_plan" in plan_body
    assert "planning_mode" in plan_body
    assert plan_body["planning_mode"]["committed_week_locked"] is True
    assert plan_body["planning_mode"]["forecast_read_only"] is True
    assert "current_week_daily_breakdown" in plan_body
    assert isinstance(plan_body["current_week_daily_breakdown"], list)
    committed = plan_body.get("committed_week_schedule")
    assert committed is not None
    current_week = int(plan_body.get("current_week", 1))
    for item in plan_body.get("forecast_plan", []):
        assert int(item.get("week", 0)) > current_week

    versions_before = client.get(f"/onboarding/plan-versions/{learner_id}")
    assert versions_before.status_code == 200
    before_count = len(versions_before.json().get("versions", []))
    assert before_count >= 1

    r = client.post(
        "/onboarding/weekly-replan",
        json={
            "learner_id": learner_id,
            "evaluation": {"chapter": "Chapter 1", "score": 0.55},
            "threshold": 0.60,
            "max_attempts": 3,
        },
    )
    assert r.status_code == 200

    versions_after = client.get(f"/onboarding/plan-versions/{learner_id}")
    assert versions_after.status_code == 200
    after_count = len(versions_after.json().get("versions", []))
    assert after_count >= before_count


def test_daily_plan_endpoint_committed_week_breakdown(client):
    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200
    bootstrap = client.get(f"/onboarding/tasks/{learner_id}")
    assert bootstrap.status_code == 200

    daily = client.get(f"/onboarding/daily-plan/{learner_id}")
    assert daily.status_code == 200
    body = daily.json()
    assert body["is_committed_week"] is True
    assert body["forecast_read_only"] is True
    assert isinstance(body.get("daily_breakdown"), list)
    if body["daily_breakdown"]:
        task_types = {slot.get("task_type") for slot in body["daily_breakdown"]}
        assert "read" in task_types
        assert "practice" in task_types
        assert "test" in task_types


def test_revision_policy_state_lifecycle_and_weak_zone_orchestration(client):
    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200

    first = client.get(f"/onboarding/revision-policy/{learner_id}")
    assert first.status_code == 200
    body1 = first.json()
    assert body1["active_pass"] == 1
    assert 0.0 <= float(body1["retention_score"]) <= 1.0
    assert isinstance(body1.get("next_actions"), list)

    low = client.post(
        "/onboarding/weekly-replan",
        json={
            "learner_id": learner_id,
            "evaluation": {"chapter": "Chapter 5", "score": 0.30},
            "threshold": 0.60,
            "max_attempts": 1,
        },
    )
    assert low.status_code == 200

    second = client.get(f"/onboarding/revision-policy/{learner_id}")
    assert second.status_code == 200
    body2 = second.json()
    assert "Chapter 5" in body2.get("weak_zones", [])


def test_engagement_telemetry_and_where_i_stand_contract(client):
    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200

    evt1 = client.post(
        "/onboarding/engagement/events",
        json={
            "learner_id": learner_id,
            "event_type": "login",
            "duration_minutes": 0,
            "details": {"source": "integration_test"},
        },
    )
    assert evt1.status_code == 200

    evt2 = client.post(
        "/onboarding/engagement/events",
        json={
            "learner_id": learner_id,
            "event_type": "study",
            "duration_minutes": 25,
            "details": {"chapter": "Chapter 1"},
        },
    )
    assert evt2.status_code == 200

    replan = client.post(
        "/onboarding/weekly-replan",
        json={
            "learner_id": learner_id,
            "evaluation": {"chapter": "Chapter 1", "score": 0.62},
            "threshold": 0.60,
            "max_attempts": 3,
        },
    )
    assert replan.status_code == 200

    summary = client.get(f"/onboarding/engagement/summary/{learner_id}")
    assert summary.status_code == 200
    summary_body = summary.json()
    assert int(summary_body.get("engagement_minutes_week", 0)) >= 25
    assert "login_streak_days" in summary_body
    assert "adherence_rate_week" in summary_body

    stand = client.get(f"/onboarding/where-i-stand/{learner_id}")
    assert stand.status_code == 200
    stand_body = stand.json()
    assert "chapter_status" in stand_body
    assert "confidence_score" in stand_body
    assert "retention_score" in stand_body

    history = client.get(f"/onboarding/profile-history/{learner_id}")
    assert history.status_code == 200
    items = history.json().get("items", [])
    assert items
    assert any(item.get("reason") in ("engagement_event", "weekly_replan") for item in items)


def test_evaluation_analytics_risk_and_recommendation_payload(client):
    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    for answer in ("wrong", "still wrong", "maybe this concept?"):
        submit = client.post(
            "/submit-answer",
            json={"session_id": session_id, "answer": answer, "response_time": 24.0},
        )
        assert submit.status_code == 200

    replan = client.post(
        "/onboarding/weekly-replan",
        json={
            "learner_id": learner_id,
            "evaluation": {"chapter": "Chapter 1", "score": 0.35},
            "threshold": 0.60,
            "max_attempts": 2,
        },
    )
    assert replan.status_code == 200

    response = client.get(f"/onboarding/evaluation-analytics/{learner_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] in ("low", "medium", "high")
    assert isinstance(body.get("recommendations"), list)
    assert isinstance(body.get("misconception_patterns"), list)
    objective = body.get("objective_evaluation", {})
    assert "avg_score" in objective
    assert "score_trend" in objective
    assert "attempted_questions" in objective
    assert isinstance(body.get("chapter_attempt_summary"), list)


def test_submit_answer_idempotency_key_returns_cached_response(client):
    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    payload = {
        "session_id": session_id,
        "answer": "stepwise attempt answer",
        "response_time": 9.0,
        "idempotency_key": "idem-submit-1",
    }
    first = client.post("/submit-answer", json=payload)
    assert first.status_code == 200
    second = client.post("/submit-answer", json=payload)
    assert second.status_code == 200
    assert second.json() == first.json()


def test_weekly_replan_idempotency_key_returns_cached_response(client):
    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200

    payload = {
        "learner_id": learner_id,
        "evaluation": {"chapter": "Chapter 7", "score": 0.45},
        "threshold": 0.60,
        "max_attempts": 3,
        "idempotency_key": "idem-replan-1",
    }
    first = client.post("/onboarding/weekly-replan", json=payload)
    assert first.status_code == 200
    second = client.post("/onboarding/weekly-replan", json=payload)
    assert second.status_code == 200
    assert second.json() == first.json()
    assert second.json()["attempt_count"] == 1


def test_ollama_unavailable_uses_template_fallback(client, monkeypatch):
    from app.api import sessions as sessions_module

    original_provider_name = getattr(sessions_module.content_agent.provider, "provider_name", "none")

    async def _broken_generate(_prompt: str):
        raise RuntimeError("ollama unavailable")

    monkeypatch.setattr(sessions_module.content_agent.provider, "generate", _broken_generate)
    monkeypatch.setattr(sessions_module.content_agent.provider, "provider_name", "ollama", raising=False)

    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200
    data = start.json()
    assert "Grounded curriculum notes" in data["explanation"]

    monkeypatch.setattr(sessions_module.content_agent.provider, "provider_name", original_provider_name, raising=False)


def test_redis_outage_falls_back_to_degraded_session_cache(client, monkeypatch):
    from app.api import sessions as sessions_module

    async def _raise(*_args, **_kwargs):
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(sessions_module.redis_client, "hset", _raise)
    monkeypatch.setattr(sessions_module.redis_client, "hgetall", _raise)
    monkeypatch.setattr(sessions_module.redis_client, "expire", _raise)

    learner_id = str(uuid.uuid4())
    start = client.post("/start-session", json={"learner_id": learner_id})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    submit = client.post(
        "/submit-answer",
        json={"session_id": session_id, "answer": "try solving", "response_time": 7.0},
    )
    assert submit.status_code == 200


def test_student_ui_surface_endpoints_available(client):
    """Smoke: API surface used by Student and Onboarding & Plan panels (critical student journey)."""
    learner_id = str(uuid.uuid4())
    # Health (shared)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"
    # Session flow
    r = client.post("/start-session", json={"learner_id": learner_id})
    assert r.status_code == 200
    assert "session_id" in r.json()
    # Plan, tasks, where-i-stand (Onboarding & Plan panel)
    r = client.get(f"/onboarding/plan/{learner_id}")
    assert r.status_code == 200
    body = r.json()
    assert "current_week_schedule" in body or "rough_plan" in body or "selected_timeline_weeks" in body
    r = client.get(f"/onboarding/tasks/{learner_id}")
    assert r.status_code == 200
    assert isinstance(r.json().get("tasks"), list)
    r = client.get(f"/onboarding/where-i-stand/{learner_id}")
    assert r.status_code == 200
    assert "chapter_status" in r.json() or "confidence_score" in r.json()


def test_admin_ui_surface_endpoints_available(client):
    """Smoke: API surface used by Admin panel (health, metrics, grounding, cohort, violations, drift)."""
    r = client.get("/health")
    assert r.status_code == 200
    r = client.get("/metrics/app")
    assert r.status_code == 200
    body = r.json()
    assert "request_count" in body and "alerts" in body and "cache" in body
    r = client.get("/grounding/status")
    assert r.status_code == 200
    assert "ready" in r.json() or "chunks" in r.json() or "status" in r.json()
    r = client.get("/admin/cohort")
    assert r.status_code == 200
    assert "learner_count" in r.json()
    r = client.get("/admin/policy-violations")
    assert r.status_code == 200
    assert "violations" in r.json()
    r = client.get("/admin/timeline-drift")
    assert r.status_code == 200
    assert "learners_with_timeline" in r.json()
