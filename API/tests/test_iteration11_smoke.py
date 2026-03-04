"""
Iteration 11 smoke checks for dashboard/comparative/reminder integrations.

Run with:
  pytest tests/test_iteration11_smoke.py -q

Requires:
  API server running at http://localhost:8000
"""

from __future__ import annotations

import time

import httpx

BASE = "http://localhost:8000"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_iteration11_student_journey_smoke():
    with httpx.Client(base_url=BASE, timeout=60) as client:
        health = client.get("/health")
        assert health.status_code == 200, health.text

        stamp = int(time.time() * 1000)
        username = f"iter11_smoke_{stamp}"
        signup_start = client.post(
            "/auth/start-signup",
            json={
                "username": username,
                "password": "testpass123",
                "name": "Iter11 Smoke",
                "date_of_birth": "2010-06-15",
                "student_email": f"{username}@example.com",
                "selected_timeline_weeks": 14,
                "math_9_percent": 67,
            },
        )
        assert signup_start.status_code in (200, 201), signup_start.text
        draft_id = signup_start.json()["signup_draft_id"]

        diag = client.post("/onboarding/diagnostic-questions", json={"signup_draft_id": draft_id})
        assert diag.status_code == 200, diag.text
        diag_payload = diag.json()
        answers = []
        for q in diag_payload.get("questions", []):
            opts = q.get("options", [])
            answers.append(
                {
                    "question_id": q["question_id"],
                    "answer": opts[0] if opts else "sample",
                }
            )

        submit = client.post(
            "/onboarding/submit",
            json={
                "signup_draft_id": draft_id,
                "diagnostic_attempt_id": diag_payload["diagnostic_attempt_id"],
                "answers": answers,
                "time_spent_minutes": 12,
            },
        )
        assert submit.status_code == 200, submit.text
        submit_payload = submit.json()
        learner_id = submit_payload["learner_id"]
        token = submit_payload["token"]

        dashboard = client.get(f"/learning/dashboard/{learner_id}", headers=_headers(token))
        assert dashboard.status_code == 200, dashboard.text
        dash = dashboard.json()
        assert "current_week" in dash
        assert "current_week_label" in dash

        comp = client.get(f"/onboarding/comparative-analytics/{learner_id}", headers=_headers(token))
        assert comp.status_code == 200, comp.text
        comp_payload = comp.json()
        assert "cohort_size" in comp_payload
        assert "comparative" in comp_payload

        rem_diag = client.get("/onboarding/reminders/diagnostics", headers=_headers(token))
        assert rem_diag.status_code == 200, rem_diag.text
        rem_payload = rem_diag.json()
        assert "dispatch_policy" in rem_payload
        assert "email" in rem_payload

        metrics = client.get("/metrics/app", headers=_headers(token))
        assert metrics.status_code == 200, metrics.text
        mcp = metrics.json().get("mcp", {})
        assert "mcp_by_operation" in mcp
