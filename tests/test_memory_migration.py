from __future__ import annotations

import importlib.util
import json
import uuid
from pathlib import Path

import pytest
from pymongo import MongoClient

from app.memory.store import FileMemoryStore, MongoMemoryStore, get_memory_runtime_status


def _can_connect_mongo(url: str = "mongodb://localhost:27017") -> bool:
    try:
        client = MongoClient(url, serverSelectionTimeoutMS=1000)
        client.admin.command("ping")
        return True
    except Exception:  # noqa: BLE001
        return False


def _load_backfill_module():
    root = Path(__file__).resolve().parents[1]
    script_path = root / "API" / "scripts" / "backfill_memory_to_mongo.py"
    spec = importlib.util.spec_from_file_location("backfill_memory_to_mongo", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not _can_connect_mongo(), reason="MongoDB is not running on localhost:27017")
def test_repository_contract_parity_file_vs_mongo(tmp_path: Path):
    file_store = FileMemoryStore(tmp_path / "file_store")
    mongo_db = f"mentorix_test_store_{uuid.uuid4().hex}"
    mongo_store = MongoMemoryStore("mongodb://localhost:27017", mongo_db)

    for store in (file_store, mongo_store):
        store.upsert_hub_entry("learner_preferences", "learner-1", {"mode": "compact"})
        store.save_snapshot({"active_runs": [{"run_id": "r1"}]})
        store.save_episode({"run_id": "r1", "nodes": [], "edges": []})

    assert file_store.get_all_hubs()["learner_preferences"]["learner-1"]["mode"] == "compact"
    assert mongo_store.get_all_hubs()["learner_preferences"]["learner-1"]["mode"] == "compact"
    assert file_store.load_latest_snapshot()["active_runs"][0]["run_id"] == "r1"
    assert mongo_store.load_latest_snapshot()["active_runs"][0]["run_id"] == "r1"


@pytest.mark.skipif(not _can_connect_mongo(), reason="MongoDB is not running on localhost:27017")
def test_mongo_index_creation_idempotency():
    mongo_db = f"mentorix_test_indexes_{uuid.uuid4().hex}"
    MongoMemoryStore("mongodb://localhost:27017", mongo_db)
    # Re-instantiating should not fail if indexes already exist.
    MongoMemoryStore("mongodb://localhost:27017", mongo_db)


@pytest.mark.skipif(not _can_connect_mongo(), reason="MongoDB is not running on localhost:27017")
def test_backfill_script_idempotency_and_parity(tmp_path: Path):
    module = _load_backfill_module()
    data_dir = tmp_path / "data" / "system"
    hubs_dir = data_dir / "structured_hubs"
    episodes_dir = data_dir / "episodes"
    hubs_dir.mkdir(parents=True, exist_ok=True)
    episodes_dir.mkdir(parents=True, exist_ok=True)

    (hubs_dir / "learner_preferences.json").write_text(
        json.dumps({"learner-1": {"preferred_explanation_density": "high"}}), encoding="utf-8"
    )
    (hubs_dir / "operating_context.json").write_text(json.dumps({"learner-1": {"recent_adaptation_score": 0.4}}), encoding="utf-8")
    (hubs_dir / "soft_identity.json").write_text(json.dumps({"learner-1": {"confidence_band": "improving"}}), encoding="utf-8")
    (data_dir / "snapshot.json").write_text(json.dumps({"active_runs": [{"run_id": "r1"}]}), encoding="utf-8")
    (episodes_dir / "skeleton_r1.json").write_text(json.dumps({"run_id": "r1", "nodes": [], "edges": []}), encoding="utf-8")

    source = module._load_file_memory(data_dir)
    mongo_db = f"mentorix_test_backfill_{uuid.uuid4().hex}"
    client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=3000)

    module._upsert_to_mongo(client, mongo_db, source)
    first_target = module._load_mongo_subset_for_parity(client, mongo_db, source)
    first_report = module._build_report(source, first_target, {"hubs_upserted": 0, "snapshots_upserted": 0, "episodes_upserted": 0}, False)
    assert first_report["parity"]["hubs_match"] is True
    assert first_report["parity"]["snapshot_match"] is True
    assert first_report["parity"]["episodes_match"] is True

    # Re-run upsert; counts in collections should stay stable (idempotent final state).
    module._upsert_to_mongo(client, mongo_db, source)
    db = client[mongo_db]
    assert db["memory_hubs"].count_documents({}) == 3
    assert db["runtime_snapshots"].count_documents({"snapshot_id": "file_snapshot_latest"}) == 1
    assert db["episodic_memory"].count_documents({"run_id": "r1"}) == 1


def test_memory_status_handles_mongo_unavailable(monkeypatch):
    from app.core import settings as settings_module

    monkeypatch.setattr(settings_module.settings, "mongodb_url", "mongodb://localhost:1")
    status = get_memory_runtime_status()
    assert "mongo" in status
    assert status["mongo"]["connected"] is False
