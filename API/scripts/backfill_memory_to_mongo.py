from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from pymongo import MongoClient


HUB_KEYS = ("learner_preferences", "operating_context", "soft_identity")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_checksum(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _load_file_memory(data_dir: Path) -> dict[str, Any]:
    hubs_dir = data_dir / "structured_hubs"
    episodes_dir = data_dir / "episodes"

    hubs = {hub: _read_json(hubs_dir / f"{hub}.json", {}) for hub in HUB_KEYS}
    snapshot = _read_json(data_dir / "snapshot.json", {})

    episodes: dict[str, dict[str, Any]] = {}
    if episodes_dir.exists():
        for episode_file in sorted(episodes_dir.glob("skeleton_*.json")):
            payload = _read_json(episode_file, {})
            run_id = str(payload.get("run_id") or episode_file.stem.replace("skeleton_", ""))
            episodes[run_id] = payload

    return {
        "hubs": hubs,
        "snapshot": snapshot,
        "episodes": episodes,
    }


def _upsert_to_mongo(client: MongoClient, db_name: str, source: dict[str, Any]) -> dict[str, int]:
    db = client[db_name]
    hubs_col = db["memory_hubs"]
    snapshots_col = db["runtime_snapshots"]
    episodes_col = db["episodic_memory"]

    hubs_upserted = 0
    for hub_type, items in source["hubs"].items():
        if not isinstance(items, dict):
            continue
        for item_key, payload in items.items():
            hubs_col.update_one(
                {"hub_type": hub_type, "item_key": str(item_key)},
                {
                    "$set": {
                        "hub_type": hub_type,
                        "item_key": str(item_key),
                        "learner_id": str(item_key),
                        "payload": payload if isinstance(payload, dict) else {},
                    }
                },
                upsert=True,
            )
            hubs_upserted += 1

    snapshots_upserted = 0
    if isinstance(source["snapshot"], dict) and source["snapshot"]:
        snapshot_doc = dict(source["snapshot"])
        snapshot_doc["snapshot_id"] = "file_snapshot_latest"
        snapshots_col.replace_one({"snapshot_id": "file_snapshot_latest"}, snapshot_doc, upsert=True)
        snapshots_upserted = 1

    episodes_upserted = 0
    for run_id, payload in source["episodes"].items():
        doc = dict(payload) if isinstance(payload, dict) else {}
        doc["run_id"] = str(run_id)
        episodes_col.replace_one({"run_id": str(run_id)}, doc, upsert=True)
        episodes_upserted += 1

    return {
        "hubs_upserted": hubs_upserted,
        "snapshots_upserted": snapshots_upserted,
        "episodes_upserted": episodes_upserted,
    }


def _mongo_hubs_subset(db, hub_keys: tuple[str, ...]) -> dict[str, dict[str, dict[str, Any]]]:
    hubs_col = db["memory_hubs"]
    hubs: dict[str, dict[str, dict[str, Any]]] = {hub: {} for hub in hub_keys}
    for hub in hub_keys:
        for doc in hubs_col.find({"hub_type": hub}, {"_id": 0, "item_key": 1, "payload": 1}):
            item_key = str(doc.get("item_key", ""))
            if not item_key:
                continue
            payload = doc.get("payload", {})
            hubs[hub][item_key] = payload if isinstance(payload, dict) else {}
    return hubs


def _mongo_snapshot_subset(db) -> dict[str, Any]:
    snapshots_col = db["runtime_snapshots"]
    snapshot = snapshots_col.find_one({"snapshot_id": "file_snapshot_latest"}, {"_id": 0})
    if not snapshot:
        return {}
    snapshot.pop("snapshot_id", None)
    return snapshot


def _mongo_episodes_subset(db, run_ids: list[str]) -> dict[str, dict[str, Any]]:
    episodes_col = db["episodic_memory"]
    episodes: dict[str, dict[str, Any]] = {}
    if not run_ids:
        return episodes
    for doc in episodes_col.find({"run_id": {"$in": run_ids}}, {"_id": 0}):
        run_id = str(doc.get("run_id", ""))
        if run_id:
            episodes[run_id] = doc
    return episodes


def _load_mongo_subset_for_parity(client: MongoClient, db_name: str, source: dict[str, Any]) -> dict[str, Any]:
    db = client[db_name]

    return {
        "hubs": _mongo_hubs_subset(db, HUB_KEYS),
        "snapshot": _mongo_snapshot_subset(db),
        "episodes": _mongo_episodes_subset(db, list(source["episodes"].keys())),
    }


def _build_report(source: dict[str, Any], target: dict[str, Any], writes: dict[str, int], dry_run: bool) -> dict[str, Any]:
    source_hub_count = sum(len(v) for v in source["hubs"].values() if isinstance(v, dict))
    target_hub_count = sum(len(v) for v in target["hubs"].values() if isinstance(v, dict))

    source_episodes_count = len(source["episodes"])
    target_episodes_count = len(target["episodes"])

    source_checksums = {
        "hubs": _canonical_checksum(source["hubs"]),
        "snapshot": _canonical_checksum(source["snapshot"]),
        "episodes": _canonical_checksum(source["episodes"]),
    }
    target_checksums = {
        "hubs": _canonical_checksum(target["hubs"]),
        "snapshot": _canonical_checksum(target["snapshot"]),
        "episodes": _canonical_checksum(target["episodes"]),
    }

    return {
        "dry_run": dry_run,
        "source_counts": {
            "hub_entries": source_hub_count,
            "has_snapshot": bool(source["snapshot"]),
            "episodes": source_episodes_count,
        },
        "mongo_counts": {
            "hub_entries": target_hub_count,
            "has_snapshot": bool(target["snapshot"]),
            "episodes": target_episodes_count,
        },
        "writes": writes,
        "checksums": {
            "source": source_checksums,
            "mongo_subset": target_checksums,
        },
        "parity": {
            "hubs_match": source_checksums["hubs"] == target_checksums["hubs"],
            "snapshot_match": source_checksums["snapshot"] == target_checksums["snapshot"],
            "episodes_match": source_checksums["episodes"] == target_checksums["episodes"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Mentorix file-based memory into MongoDB.")
    parser.add_argument("--data-dir", default="data/system", help="Path to file memory root directory.")
    parser.add_argument("--mongodb-url", default="mongodb://localhost:27017", help="MongoDB connection URL.")
    parser.add_argument("--db-name", default="mentorix", help="MongoDB database name.")
    parser.add_argument(
        "--report-path",
        default="data/system/reports/memory_backfill_report.json",
        help="Path to write parity report JSON.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Compute parity report without writing to MongoDB.")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    source = _load_file_memory(data_dir)

    writes = {"hubs_upserted": 0, "snapshots_upserted": 0, "episodes_upserted": 0}
    client = MongoClient(args.mongodb_url, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")

    if not args.dry_run:
        writes = _upsert_to_mongo(client, args.db_name, source)

    target = _load_mongo_subset_for_parity(client, args.db_name, source)
    report = _build_report(source, target, writes, args.dry_run)

    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
