"""
Pytest configuration for API tests.

Set env before any app import so memory store uses file backend (no pymongo required).
"""
from __future__ import annotations

import os

os.environ.setdefault("MEMORY_STORE_BACKEND", "file")
os.environ.setdefault("MEMORY_DUAL_WRITE", "false")
