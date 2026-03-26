"""
Environment-aware secret management — multi-backend secret provider.

Supports:
- Environment variables (default, zero-config)
- AWS Secrets Manager (via boto3)
- HashiCorp Vault (via hvac)

Backend auto-detected from SECRET_BACKEND env variable.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from app.core.logging import get_domain_logger

logger = get_domain_logger(__name__, "security")


# ── Backend enum ─────────────────────────────────────────────────────

BACKEND_ENV = "env"
BACKEND_AWS = "aws_secrets_manager"
BACKEND_VAULT = "hashicorp_vault"


# ── Cache ────────────────────────────────────────────────────────────

_cache: dict[str, tuple[str, float]] = {}
DEFAULT_CACHE_TTL = 300.0  # 5 minutes


def _is_cached(key: str, ttl: float = DEFAULT_CACHE_TTL) -> str | None:
    """Return cached value if not expired."""
    if key in _cache:
        value, timestamp = _cache[key]
        if time.time() - timestamp < ttl:
            return value
        del _cache[key]
    return None


def _set_cache(key: str, value: str) -> None:
    """Store a value in the cache."""
    _cache[key] = (value, time.time())


# ── Environment backend (default) ────────────────────────────────────

def _get_from_env(key: str, default: str = "") -> str:
    """Read secret from environment variable."""
    return os.environ.get(key, default)


# ── AWS Secrets Manager backend ──────────────────────────────────────

def _get_from_aws(key: str, default: str = "") -> str:
    """Read secret from AWS Secrets Manager."""
    try:
        import boto3
        import json

        client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        response = client.get_secret_value(SecretId=key)
        secret_string = response.get("SecretString", "")
        # Try JSON parse (key-value secrets)
        try:
            parsed = json.loads(secret_string)
            return str(parsed.get(key, secret_string))
        except (json.JSONDecodeError, ValueError):
            return secret_string
    except ImportError:
        logger.warning("event=aws_secrets_unavailable reason=boto3_not_installed")
        return _get_from_env(key, default)
    except Exception as exc:
        logger.warning("event=aws_secret_failed key=%s error=%s", key, exc)
        return _get_from_env(key, default)


# ── HashiCorp Vault backend ─────────────────────────────────────────

def _get_from_vault(key: str, default: str = "") -> str:
    """Read secret from HashiCorp Vault."""
    try:
        import hvac

        vault_url = os.environ.get("VAULT_ADDR", "http://localhost:8200")
        vault_token = os.environ.get("VAULT_TOKEN", "")
        vault_path = os.environ.get("VAULT_SECRET_PATH", "secret/data/mentorix")

        client = hvac.Client(url=vault_url, token=vault_token)
        response = client.secrets.kv.v2.read_secret_version(path=vault_path)
        data = response.get("data", {}).get("data", {})
        return str(data.get(key, default))
    except ImportError:
        logger.warning("event=vault_unavailable reason=hvac_not_installed")
        return _get_from_env(key, default)
    except Exception as exc:
        logger.warning("event=vault_secret_failed key=%s error=%s", key, exc)
        return _get_from_env(key, default)


# ── Public API ───────────────────────────────────────────────────────

def get_secret(
    key: str,
    default: str = "",
    *,
    cache_ttl: float = DEFAULT_CACHE_TTL,
) -> str:
    """
    Retrieve a secret value using the configured backend.

    Checks cache first, then delegates to the backend specified by
    ``SECRET_BACKEND`` environment variable.
    """
    # Check cache
    cached = _is_cached(key, cache_ttl)
    if cached is not None:
        return cached

    backend = os.environ.get("SECRET_BACKEND", BACKEND_ENV).lower()

    if backend == BACKEND_AWS:
        value = _get_from_aws(key, default)
    elif backend == BACKEND_VAULT:
        value = _get_from_vault(key, default)
    else:
        value = _get_from_env(key, default)

    if value:
        _set_cache(key, value)

    return value


def clear_cache() -> None:
    """Clear the secret cache (useful for key rotation)."""
    _cache.clear()
    logger.info("event=secret_cache_cleared")


def get_secret_backend() -> str:
    """Return the current secret backend name."""
    return os.environ.get("SECRET_BACKEND", BACKEND_ENV).lower()


def get_cache_stats() -> dict[str, Any]:
    """Return cache statistics."""
    now = time.time()
    return {
        "backend": get_secret_backend(),
        "cached_keys": len(_cache),
        "keys": [
            {"key": k, "age_seconds": round(now - ts, 1)}
            for k, (_, ts) in _cache.items()
        ],
    }
