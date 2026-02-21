from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "API"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as tc:
        yield tc
