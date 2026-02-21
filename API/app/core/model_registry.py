import json
from pathlib import Path

from app.core.settings import settings


DEFAULT_MODEL_REGISTRY = {
    "models": {
        "gemini-flash": {"provider": "gemini", "model": "gemini-2.5-flash"},
        "gemini-lite": {"provider": "gemini", "model": "gemini-2.5-flash"},
        "local-verifier": {"provider": "ollama", "model": "phi4-mini"},
    },
    "roles": {
        "planner": "gemini-flash",
        "content_generator": "gemini-flash",
        "optimizer": "gemini-lite",
        "verifier": "local-verifier",
    },
    "settings": {
        "enforce_local_verifier": False,
    },
}


def _registry_path() -> Path:
    workspace_root = Path(__file__).resolve().parents[3]
    configured = Path(settings.model_registry_file)
    return configured if configured.is_absolute() else workspace_root / configured


def load_model_registry() -> dict:
    path = _registry_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULT_MODEL_REGISTRY, indent=2), encoding="utf-8")
        return DEFAULT_MODEL_REGISTRY
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_role(role: str | None) -> dict:
    registry = load_model_registry()
    roles = registry.get("roles", {})
    models = registry.get("models", {})
    settings_blob = registry.get("settings", {})
    role_key = role or "content_generator"
    alias = roles.get(role_key, "gemini-flash")
    resolved = models.get(alias, models.get("gemini-flash", {})).copy()
    resolved["role"] = role_key

    enforce_local = bool(settings_blob.get("enforce_local_verifier", False)) or settings.enforce_local_verifier
    if role_key == "verifier" and enforce_local and resolved.get("provider") != "ollama":
        raise ValueError("Policy violation: verifier must be local")

    return resolved
