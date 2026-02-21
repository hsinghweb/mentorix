import json
from datetime import datetime
from pathlib import Path

from app.core.settings import settings
from app.runtime.run_manager import run_manager


class SnapshotPersistence:
    def __init__(self):
        self.base = Path(settings.runtime_data_dir)
        self.snapshot_file = self.base / "snapshot.json"

    def save_snapshot(self) -> None:
        self.base.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "active_runs": run_manager.list_runs(),
        }
        self.snapshot_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_snapshot(self) -> dict:
        if not self.snapshot_file.exists():
            return {"active_runs": []}
        return json.loads(self.snapshot_file.read_text(encoding="utf-8"))


snapshot_persistence = SnapshotPersistence()
