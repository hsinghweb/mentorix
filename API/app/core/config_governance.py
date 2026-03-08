"""
Config Governance — validates configuration consistency at startup.

Detects drift between declared agent/tool capabilities and actual runtime config.
Validates schema contracts and provides migration-safe defaults.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.core.model_registry import load_model_registry
from app.core.settings import settings

logger = logging.getLogger(__name__)


class ConfigDriftError(Exception):
    """Raised when startup config drift is detected."""


# --- Expected contracts ---
REQUIRED_ROLE_KEYS = {"planner", "content_generator", "optimizer", "verifier"}
REQUIRED_MODEL_FIELDS = {"id", "provider"}
REQUIRED_SETTINGS_FIELDS = {
    "llm_provider",
    "llm_model",
    "database_url",
    "embedding_provider",
    "embedding_model",
}


def validate_model_registry() -> list[str]:
    """Return list of drift errors found in the model registry."""
    errors: list[str] = []
    registry = load_model_registry()
    roles = registry.get("roles", {})
    models = registry.get("models", {})

    # Check all required roles exist
    for role in REQUIRED_ROLE_KEYS:
        if role not in roles:
            errors.append(f"Missing role '{role}' in model registry")
        else:
            alias = roles[role]
            if alias not in models:
                errors.append(
                    f"Role '{role}' maps to alias '{alias}' which is not in models"
                )

    # Check model entries have required fields
    for alias, model_def in models.items():
        for field in REQUIRED_MODEL_FIELDS:
            if field not in model_def:
                errors.append(f"Model '{alias}' missing required field '{field}'")

    return errors


def validate_settings() -> list[str]:
    """Validate that critical settings are non-empty."""
    errors: list[str] = []
    for field_name in REQUIRED_SETTINGS_FIELDS:
        value = getattr(settings, field_name, None)
        if not value or (isinstance(value, str) and not value.strip()):
            errors.append(f"Setting '{field_name}' is empty or missing")
    return errors


def validate_all(*, fail_fast: bool = True) -> list[str]:
    """
    Run all config validations.

    If fail_fast is True (default), raises ConfigDriftError on first batch of errors.
    Returns the list of all errors found.
    """
    errors: list[str] = []
    errors.extend(validate_model_registry())
    errors.extend(validate_settings())

    if errors:
        for err in errors:
            logger.error("Config drift: %s", err)
        if fail_fast:
            raise ConfigDriftError(
                f"Startup config drift detected ({len(errors)} errors): "
                + "; ".join(errors[:5])
            )
    else:
        logger.info("Config governance: all validations passed")

    return errors
