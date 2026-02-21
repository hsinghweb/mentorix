from __future__ import annotations

import json
from pathlib import Path

from app.core.settings import settings


class StructuredMemoryHubs:
    def __init__(self):
        self.base = Path(settings.runtime_data_dir) / "structured_hubs"
        self.base.mkdir(parents=True, exist_ok=True)
        self.files = {
            "learner_preferences": self.base / "learner_preferences.json",
            "operating_context": self.base / "operating_context.json",
            "soft_identity": self.base / "soft_identity.json",
        }
        for file in self.files.values():
            if not file.exists():
                file.write_text("{}", encoding="utf-8")

    def _read(self, key: str) -> dict:
        return json.loads(self.files[key].read_text(encoding="utf-8"))

    def _write(self, key: str, payload: dict) -> None:
        self.files[key].write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def upsert(self, key: str, item_key: str, payload: dict) -> None:
        data = self._read(key)
        data[item_key] = payload
        self._write(key, data)

    def get_all(self) -> dict:
        return {key: self._read(key) for key in self.files}


structured_hubs = StructuredMemoryHubs()
