from datetime import datetime, timezone

from app.memory.store import memory_store
from app.runtime.run_manager import run_manager


class SnapshotPersistence:
    def save_snapshot(self) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_runs": run_manager.list_runs(),
        }
        memory_store.save_snapshot(payload)

    def load_snapshot(self) -> dict:
        return memory_store.load_latest_snapshot()


snapshot_persistence = SnapshotPersistence()
