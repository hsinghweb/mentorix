import uuid

from app.core.logging import redact_secrets


def test_redact_secrets_masks_sensitive_values():
    raw = (
        "authorization=Bearer abc123 "
        "x-goog-api-key=AIzaSySecret "
        "api_key=my-api-key "
        "token=my-token password=my-password"
    )
    masked = redact_secrets(raw)
    assert "abc123" not in masked
    assert "AIzaSySecret" not in masked
    assert "my-api-key" not in masked
    assert "my-token" not in masked
    assert "my-password" not in masked
    assert masked.count("[REDACTED]") >= 5


def test_gateway_auth_enabled_path_requires_api_key(client, monkeypatch):
    from app.core.settings import settings

    monkeypatch.setattr(settings, "gateway_auth_enabled", True)
    monkeypatch.setattr(settings, "gateway_api_key", "test-key")

    learner_id = str(uuid.uuid4())
    blocked = client.post("/start-session", json={"learner_id": learner_id})
    assert blocked.status_code == 401
    assert "missing x-api-key" in str(blocked.json())

    allowed = client.post("/start-session", json={"learner_id": learner_id}, headers={"x-api-key": "test-key"})
    assert allowed.status_code == 200

    monkeypatch.setattr(settings, "gateway_auth_enabled", False)
    monkeypatch.setattr(settings, "gateway_api_key", "")


def test_db_outage_returns_error_envelope(client, monkeypatch):
    from app.api import sessions as sessions_module

    async def _raise_db(*_args, **_kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(sessions_module, "_get_or_create_learner_profile", _raise_db)
    response = client.post("/start-session", json={"learner_id": str(uuid.uuid4())})
    assert response.status_code == 503
    body = response.json()
    assert body.get("success") is False
    assert body.get("error", {}).get("code") == "http_error"
