from __future__ import annotations

import json
from pathlib import Path

from app.core.settings import settings


class MemorySkeletonizer:
    @staticmethod
    def skeletonize(run_payload: dict) -> dict:
        nodes = run_payload.get("nodes", [])
        edges = run_payload.get("edges", [])
        compressed_nodes = []
        for node in nodes:
            compressed = {
                "id": node.get("id"),
                "agent": node.get("agent"),
                "description": node.get("description"),
                "status": node.get("status"),
                "error": node.get("error"),
                "reads": node.get("reads", []),
                "writes": node.get("writes", []),
            }
            if node.get("agent_prompt"):
                compressed["logic_prompt"] = node.get("agent_prompt")
            output = node.get("output") or {}
            if isinstance(output, dict):
                logic = {}
                for key in ("thought", "reasoning", "_optimized_query", "_reasoning_trace", "adaptation_score"):
                    if key in output:
                        logic[key] = output[key]
                if logic:
                    compressed["logic"] = logic
            iterations = node.get("iterations") or []
            actions = []
            if isinstance(iterations, list):
                for iteration in iterations:
                    i_output = (iteration or {}).get("output", {})
                    if not isinstance(i_output, dict):
                        continue
                    tool_call = i_output.get("call_tool")
                    if isinstance(tool_call, dict):
                        actions.append(
                            {
                                "type": "tool",
                                "name": tool_call.get("name"),
                                "args": str(tool_call.get("arguments", ""))[:200],
                            }
                        )
                    self_call = i_output.get("call_self")
                    if isinstance(self_call, dict):
                        actions.append(
                            {
                                "type": "code",
                                "lang": "python",
                                "snippet": str(self_call.get("code", ""))[:500],
                            }
                        )
            if actions:
                compressed["actions"] = actions
            compressed_nodes.append(compressed)

        return {
            "run_id": run_payload.get("run_id"),
            "query": run_payload.get("query"),
            "status": run_payload.get("status"),
            "updated_at": run_payload.get("updated_at"),
            "nodes": compressed_nodes,
            "edges": edges,
        }


class EpisodicMemory:
    def __init__(self):
        self.base = Path(settings.runtime_data_dir) / "episodes"
        self.base.mkdir(parents=True, exist_ok=True)

    def save_episode(self, run_payload: dict) -> Path:
        skeleton = MemorySkeletonizer.skeletonize(run_payload)
        run_id = skeleton.get("run_id") or "unknown"
        target = self.base / f"skeleton_{run_id}.json"
        target.write_text(json.dumps(skeleton, indent=2), encoding="utf-8")
        return target


episodic_memory = EpisodicMemory()
