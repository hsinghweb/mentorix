from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from app.core.settings import settings

HUB_KEYS = ("learner_preferences", "operating_context", "soft_identity")


class MemoryStore(ABC):
    @abstractmethod
    def upsert_hub_entry(self, hub_type: str, item_key: str, payload: dict, learner_id: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_all_hubs(self) -> dict[str, dict]:
        raise NotImplementedError

    @abstractmethod
    def save_snapshot(self, payload: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_latest_snapshot(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def save_episode(self, skeleton: dict) -> None:
        raise NotImplementedError


class FileMemoryStore(MemoryStore):
    def __init__(self, base_dir: Path):
        self.base = base_dir
        self.base.mkdir(parents=True, exist_ok=True)
        self.hubs_base = self.base / "structured_hubs"
        self.hubs_base.mkdir(parents=True, exist_ok=True)
        self.episodes_base = self.base / "episodes"
        self.episodes_base.mkdir(parents=True, exist_ok=True)
        self.snapshot_file = self.base / "snapshot.json"
        self.hub_files = {hub: self.hubs_base / f"{hub}.json" for hub in HUB_KEYS}
        for file_path in self.hub_files.values():
            if not file_path.exists():
                file_path.write_text("{}", encoding="utf-8")

    @staticmethod
    def _read_json(path: Path, default: dict | None = None) -> dict:
        if not path.exists():
            return default or {}
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def upsert_hub_entry(self, hub_type: str, item_key: str, payload: dict, learner_id: str | None = None) -> None:
        if hub_type not in self.hub_files:
            raise ValueError(f"Unsupported hub_type: {hub_type}")
        existing = self._read_json(self.hub_files[hub_type], {})
        existing[item_key] = payload
        self._write_json(self.hub_files[hub_type], existing)

    def get_all_hubs(self) -> dict[str, dict]:
        return {hub: self._read_json(self.hub_files[hub], {}) for hub in HUB_KEYS}

    def save_snapshot(self, payload: dict) -> None:
        self._write_json(self.snapshot_file, payload)

    def load_latest_snapshot(self) -> dict:
        return self._read_json(self.snapshot_file, {"active_runs": []})

    def save_episode(self, skeleton: dict) -> None:
        run_id = str(skeleton.get("run_id") or "unknown")
        target = self.episodes_base / f"skeleton_{run_id}.json"
        self._write_json(target, skeleton)


class MongoMemoryStore(MemoryStore):
    def __init__(self, mongodb_url: str, db_name: str):
        from pymongo import ASCENDING, DESCENDING, MongoClient

        self._ASC = ASCENDING
        self._DESC = DESCENDING
        self._client = MongoClient(mongodb_url, serverSelectionTimeoutMS=3000)
        self._db = self._client[db_name]
        self._hubs = self._db["memory_hubs"]
        self._snapshots = self._db["runtime_snapshots"]
        self._episodes = self._db["episodic_memory"]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self._hubs.create_index(
            [("hub_type", self._ASC), ("item_key", self._ASC)],
            unique=True,
            name="ux_hub_type_item_key",
        )
        self._hubs.create_index([("learner_id", self._ASC)], name="ix_hubs_learner_id")
        self._snapshots.create_index([("timestamp", self._DESC)], name="ix_snapshots_timestamp_desc")
        self._episodes.create_index([("run_id", self._ASC)], unique=True, name="ux_episodes_run_id")
        self._episodes.create_index([("updated_at", self._DESC)], name="ix_episodes_updated_at_desc")

    def upsert_hub_entry(self, hub_type: str, item_key: str, payload: dict, learner_id: str | None = None) -> None:
        if hub_type not in HUB_KEYS:
            raise ValueError(f"Unsupported hub_type: {hub_type}")
        now = datetime.now(datetime.UTC).isoformat()
        self._hubs.update_one(
            {"hub_type": hub_type, "item_key": item_key},
            {
                "$set": {
                    "payload": payload,
                    "learner_id": learner_id,
                    "updated_at": now,
                }
            },
            upsert=True,
        )

    def get_all_hubs(self) -> dict[str, dict]:
        out = {hub: {} for hub in HUB_KEYS}
        for doc in self._hubs.find({}, {"_id": 0, "hub_type": 1, "item_key": 1, "payload": 1}):
            hub_type = str(doc.get("hub_type", ""))
            item_key = str(doc.get("item_key", ""))
            payload = doc.get("payload", {})
            if hub_type in out and item_key:
                out[hub_type][item_key] = payload if isinstance(payload, dict) else {}
        return out

    def save_snapshot(self, payload: dict) -> None:
        doc = dict(payload)
        doc.setdefault("timestamp", datetime.now(datetime.UTC).isoformat())
        self._snapshots.insert_one(doc)

    def load_latest_snapshot(self) -> dict:
        latest = self._snapshots.find_one(sort=[("timestamp", -1)])
        if not latest:
            return {"active_runs": []}
        latest.pop("_id", None)
        return latest

    def save_episode(self, skeleton: dict) -> None:
        run_id = str(skeleton.get("run_id") or "unknown")
        doc = dict(skeleton)
        doc["run_id"] = run_id
        self._episodes.replace_one({"run_id": run_id}, doc, upsert=True)


def build_memory_store() -> MemoryStore:
    backend = settings.memory_store_backend.strip().lower()
    if backend == "mongo":
        return MongoMemoryStore(settings.mongodb_url, settings.mongodb_db_name)
    return FileMemoryStore(Path(settings.runtime_data_dir))


memory_store = build_memory_store()

