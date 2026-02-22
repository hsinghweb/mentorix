from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from app.core.settings import settings

HUB_KEYS = ("learner_preferences", "operating_context", "soft_identity")
logger = logging.getLogger(__name__)
SENSITIVE_KEYS = {"password", "pass", "passwd", "secret", "token", "api_key", "authorization"}


def _redact_payload(value):
    if isinstance(value, dict):
        output = {}
        for key, inner in value.items():
            key_lower = str(key).lower()
            if key_lower in SENSITIVE_KEYS:
                output[key] = "***REDACTED***"
            else:
                output[key] = _redact_payload(inner)
        return output
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    return value


def _sanitize_mongo_error(raw: str) -> str:
    if not raw:
        return raw
    # Hide credentials embedded in connection URLs.
    return re.sub(r"(mongodb(?:\+srv)?://)([^/@\s]+)@", r"\1***:***@", raw)


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
        existing[item_key] = _redact_payload(payload)
        self._write_json(self.hub_files[hub_type], existing)

    def get_all_hubs(self) -> dict[str, dict]:
        return {hub: self._read_json(self.hub_files[hub], {}) for hub in HUB_KEYS}

    def save_snapshot(self, payload: dict) -> None:
        self._write_json(self.snapshot_file, _redact_payload(payload))

    def load_latest_snapshot(self) -> dict:
        return self._read_json(self.snapshot_file, {"active_runs": []})

    def save_episode(self, skeleton: dict) -> None:
        run_id = str(skeleton.get("run_id") or "unknown")
        target = self.episodes_base / f"skeleton_{run_id}.json"
        self._write_json(target, _redact_payload(skeleton))


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
        if settings.mongodb_snapshots_ttl_days > 0:
            self._snapshots.create_index(
                [("timestamp_dt", self._DESC)],
                name="ix_snapshots_timestamp_dt_ttl",
                expireAfterSeconds=int(settings.mongodb_snapshots_ttl_days) * 86400,
            )
        if settings.mongodb_episodes_ttl_days > 0:
            self._episodes.create_index(
                [("updated_at_dt", self._DESC)],
                name="ix_episodes_updated_at_dt_ttl",
                expireAfterSeconds=int(settings.mongodb_episodes_ttl_days) * 86400,
            )

    def upsert_hub_entry(self, hub_type: str, item_key: str, payload: dict, learner_id: str | None = None) -> None:
        if hub_type not in HUB_KEYS:
            raise ValueError(f"Unsupported hub_type: {hub_type}")
        now = datetime.now(timezone.utc).isoformat()
        self._hubs.update_one(
            {"hub_type": hub_type, "item_key": item_key},
            {
                "$set": {
                    "payload": _redact_payload(payload),
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
        doc.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        doc.setdefault("timestamp_dt", datetime.now(timezone.utc))
        self._snapshots.insert_one(doc)

    def load_latest_snapshot(self) -> dict:
        latest = self._snapshots.find_one(sort=[("timestamp", -1)])
        if not latest:
            return {"active_runs": []}
        latest.pop("_id", None)
        return latest

    def save_episode(self, skeleton: dict) -> None:
        run_id = str(skeleton.get("run_id") or "unknown")
        doc = _redact_payload(dict(skeleton))
        doc["run_id"] = run_id
        doc["updated_at_dt"] = datetime.now(timezone.utc)
        self._episodes.replace_one({"run_id": run_id}, doc, upsert=True)


class DualWriteMemoryStore(MemoryStore):
    """
    Phase-B migration mode:
    - reads remain on file store
    - writes go to file + mongo
    """

    def __init__(self, read_store: MemoryStore, primary_write_store: MemoryStore, secondary_write_store: MemoryStore):
        self._read_store = read_store
        self._primary = primary_write_store
        self._secondary = secondary_write_store

    def _write_both(self, op_name: str, primary_call, secondary_call) -> None:
        primary_call()
        try:
            secondary_call()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Dual-write secondary write failed op=%s error=%s", op_name, str(exc))

    def upsert_hub_entry(self, hub_type: str, item_key: str, payload: dict, learner_id: str | None = None) -> None:
        self._write_both(
            "upsert_hub_entry",
            lambda: self._primary.upsert_hub_entry(hub_type, item_key, payload, learner_id=learner_id),
            lambda: self._secondary.upsert_hub_entry(hub_type, item_key, payload, learner_id=learner_id),
        )

    def get_all_hubs(self) -> dict[str, dict]:
        file_payload = self._read_store.get_all_hubs()
        try:
            mongo_payload = self._secondary.get_all_hubs()
            if file_payload != mongo_payload:
                logger.info("Dual-write parity check: memory hubs differ between file and mongo stores")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Dual-write parity check failed for hubs error=%s", str(exc))
        return file_payload

    def save_snapshot(self, payload: dict) -> None:
        self._write_both(
            "save_snapshot",
            lambda: self._primary.save_snapshot(payload),
            lambda: self._secondary.save_snapshot(payload),
        )

    def load_latest_snapshot(self) -> dict:
        file_payload = self._read_store.load_latest_snapshot()
        try:
            mongo_payload = self._secondary.load_latest_snapshot()
            if bool(file_payload) != bool(mongo_payload):
                logger.info("Dual-write parity check: snapshot presence differs between file and mongo stores")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Dual-write parity check failed for snapshots error=%s", str(exc))
        return file_payload

    def save_episode(self, skeleton: dict) -> None:
        self._write_both(
            "save_episode",
            lambda: self._primary.save_episode(skeleton),
            lambda: self._secondary.save_episode(skeleton),
        )


def build_memory_store() -> MemoryStore:
    backend = settings.memory_store_backend.strip().lower()
    dual_write = settings.memory_dual_write
    file_store = FileMemoryStore(Path(settings.runtime_data_dir))

    if dual_write:
        mongo_store = MongoMemoryStore(settings.mongodb_url, settings.mongodb_db_name)
        if backend != "file":
            logger.warning(
                "MEMORY_DUAL_WRITE=true forces file-read migration mode. "
                "Current MEMORY_STORE_BACKEND=%s; reads will still come from file store.",
                backend,
            )
        return DualWriteMemoryStore(
            read_store=file_store,
            primary_write_store=file_store,
            secondary_write_store=mongo_store,
        )

    if backend == "mongo":
        return MongoMemoryStore(settings.mongodb_url, settings.mongodb_db_name)
    return file_store


memory_store = build_memory_store()


def _mongo_ping() -> tuple[bool, str | None]:
    try:
        from pymongo import MongoClient

        client = MongoClient(settings.mongodb_url, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, _sanitize_mongo_error(str(exc))


def get_memory_runtime_status() -> dict:
    configured_backend = settings.memory_store_backend.strip().lower()
    dual_write_enabled = settings.memory_dual_write

    if dual_write_enabled:
        active_mode = "dual_write_file_read"
    elif isinstance(memory_store, MongoMemoryStore):
        active_mode = "mongo"
    else:
        active_mode = "file"

    mongo_ok, mongo_error = _mongo_ping()
    return {
        "configured_backend": configured_backend,
        "active_mode": active_mode,
        "dual_write_enabled": dual_write_enabled,
        "mongo": {
            "connected": mongo_ok,
            "db_name": settings.mongodb_db_name,
            "error": mongo_error,
        },
    }

