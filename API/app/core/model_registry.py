import json
from pathlib import Path

from app.core.settings import settings


DEFAULT_MODEL_REGISTRY = {
    "models": {
        "gemini-flash": {
            "id": "gemini-2.5-flash",
            "provider": "gemini",
            "cost_per_1k": 0.0001,
            "context_window": 1000000,
        },
        "gemini-lite": {
            "id": "gemini-2.5-flash",
            "provider": "gemini",
            "cost_per_1k": 0.0001,
            "context_window": 1000000,
        },
        "local-verifier": {
            "id": "phi4-mini",
            "provider": "ollama",
            "cost_per_1k": 0.0,
            "context_window": 128000,
        },
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


class PolicyViolation(Exception):
    """Raised when model governance policy is violated."""


def _registry_path() -> Path:
    workspace_root = Path(__file__).resolve().parents[3]
    configured = Path(settings.model_registry_file)
    return configured if configured.is_absolute() else workspace_root / configured


def _try_parse_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        return loaded or {}
    except Exception:
        return {}


def load_model_registry() -> dict:
    path = _registry_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULT_MODEL_REGISTRY, indent=2), encoding="utf-8")
        return DEFAULT_MODEL_REGISTRY

    if path.suffix.lower() in {".yaml", ".yml"}:
        parsed = _try_parse_yaml(path)
        if parsed:
            return parsed
        return DEFAULT_MODEL_REGISTRY

    # Optional YAML sidecar override if present.
    yaml_sidecar = path.with_suffix(".yaml")
    if yaml_sidecar.exists():
        parsed = _try_parse_yaml(yaml_sidecar)
        if parsed:
            return parsed

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
    resolved["alias"] = alias
    resolved["model"] = resolved.get("model") or resolved.get("id")

    enforce_local = bool(settings_blob.get("enforce_local_verifier", False)) or settings.enforce_local_verifier
    if role_key == "verifier" and enforce_local and resolved.get("provider") != "ollama":
        raise PolicyViolation("Verifier MUST be local due to enforce_local_verifier policy")

    return resolved
