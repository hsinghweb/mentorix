from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "API"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

# Test-mode runtime guards:
# - no external LLM/embedding traffic
# - deterministic local fallback behavior
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LLM_PROVIDER", "none")
os.environ.setdefault("ROLE_MODEL_GOVERNANCE_ENABLED", "false")
os.environ.setdefault("EMBEDDING_PROVIDER", "local")
os.environ.setdefault("INCLUDE_GENERATED_ARTIFACTS_IN_RETRIEVAL", "false")
os.environ.setdefault("GROUNDING_PREPARE_ON_START", "false")
os.environ.setdefault("GROUNDING_REQUIRE_READY", "false")

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as tc:
        yield tc
