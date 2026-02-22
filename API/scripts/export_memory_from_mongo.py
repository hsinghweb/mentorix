from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pymongo import MongoClient


HUB_KEYS = ("learner_preferences", "operating_context", "soft_identity")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _export_hubs(db) -> dict[str, dict[str, dict[str, Any]]]:
    hubs_col = db["memory_hubs"]
    hubs = {hub: {} for hub in HUB_KEYS}
    for hub in HUB_KEYS:
        for doc in hubs_col.find({"hub_type": hub}, {"_id": 0, "item_key": 1, "payload": 1}):
            item_key = str(doc.get("item_key", ""))
            if not item_key:
                continue
            payload = doc.get("payload", {})
            hubs[hub][item_key] = payload if isinstance(payload, dict) else {}
    return hubs


def _export_snapshot(db) -> dict[str, Any]:
    snapshots_col = db["runtime_snapshots"]
    snapshot = snapshots_col.find_one(sort=[("timestamp", -1)])
    if not snapshot:
        return {}
    snapshot.pop("_id", None)
    snapshot.pop("snapshot_id", None)
    return snapshot


def _export_episodes(db) -> dict[str, dict[str, Any]]:
    episodes_col = db["episodic_memory"]
    episodes: dict[str, dict[str, Any]] = {}
    for doc in episodes_col.find({}, {"_id": 0}):
        run_id = str(doc.get("run_id", ""))
        if run_id:
            episodes[run_id] = doc
    return episodes


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Mentorix memory documents from MongoDB to JSON files.")
    parser.add_argument("--mongodb-url", default="mongodb://localhost:27017", help="MongoDB connection URL.")
    parser.add_argument("--db-name", default="mentorix", help="MongoDB database name.")
    parser.add_argument("--out-dir", default="data/system/export_from_mongo", help="Directory to write export files.")
    args = parser.parse_args()

    client = MongoClient(args.mongodb_url, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[args.db_name]

    out_dir = Path(args.out_dir)
    hubs = _export_hubs(db)
    snapshot = _export_snapshot(db)
    episodes = _export_episodes(db)

    hubs_dir = out_dir / "structured_hubs"
    for hub, payload in hubs.items():
        _write_json(hubs_dir / f"{hub}.json", payload)

    _write_json(out_dir / "snapshot.json", snapshot)

    episodes_dir = out_dir / "episodes"
    for run_id, payload in episodes.items():
        _write_json(episodes_dir / f"skeleton_{run_id}.json", payload)

    summary = {
        "output_dir": str(out_dir),
        "hub_entries": sum(len(items) for items in hubs.values()),
        "has_snapshot": bool(snapshot),
        "episodes": len(episodes),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
