from __future__ import annotations

from app.memory.store import HUB_KEYS, memory_store


class StructuredMemoryHubs:
    def upsert(self, key: str, item_key: str, payload: dict) -> None:
        if key not in HUB_KEYS:
            raise ValueError(f"Unsupported hub key: {key}")
        memory_store.upsert_hub_entry(key, item_key, payload, learner_id=item_key)

    def get_all(self) -> dict:
        return memory_store.get_all_hubs()


structured_hubs = StructuredMemoryHubs()
