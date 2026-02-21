from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class RuntimeNode:
    id: str
    agent: str
    description: str
    reads: list[str] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)
    status: str = "pending"
    output: dict | None = None
    error: str | None = None
    retries: int = 0
    start_time: str | None = None
    end_time: str | None = None


class GraphExecutionContext:
    def __init__(self, *, query: str, nodes: list[RuntimeNode], edges: list[tuple[str, str]], run_id: str | None = None):
        self.run_id = run_id or str(uuid.uuid4())
        self.query = query
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = self.created_at
        self.status = "running"
        self.stop_requested = False
        self.nodes: dict[str, RuntimeNode] = {n.id: n for n in nodes}
        self.edges = edges
        self.globals_schema: dict[str, object] = {"query": query}
        self.metadata: dict[str, object] = {}

    def predecessors(self, node_id: str) -> list[str]:
        return [u for u, v in self.edges if v == node_id]

    def ready_steps(self) -> list[str]:
        ready: list[str] = []
        for node in self.nodes.values():
            if node.status != "pending":
                continue
            if all(self.nodes[p].status == "completed" for p in self.predecessors(node.id)):
                ready.append(node.id)
        return ready

    def all_done(self) -> bool:
        return all(node.status in {"completed", "failed", "skipped", "stopped"} for node in self.nodes.values())

    def mark_running(self, node_id: str) -> None:
        node = self.nodes[node_id]
        node.status = "running"
        node.start_time = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()

    def mark_done(self, node_id: str, output: dict) -> None:
        node = self.nodes[node_id]
        node.status = "completed"
        node.output = output
        node.end_time = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()
        for write_key in node.writes:
            if write_key in output:
                self.globals_schema[write_key] = output[write_key]

    def mark_failed(self, node_id: str, error: str) -> None:
        node = self.nodes[node_id]
        node.status = "failed"
        node.error = error
        node.end_time = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()

    def inputs_for(self, node_id: str) -> dict:
        node = self.nodes[node_id]
        return {k: self.globals_schema.get(k) for k in node.reads}

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "query": self.query,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "globals_schema": self.globals_schema,
            "nodes": [vars(node) for node in self.nodes.values()],
            "edges": [{"source": s, "target": t} for s, t in self.edges],
            "metadata": self.metadata,
        }

    def save(self, base_dir: Path) -> Path:
        base_dir.mkdir(parents=True, exist_ok=True)
        target = base_dir / f"run_{self.run_id}.json"
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return target
