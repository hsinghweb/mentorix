from app.runtime.graph_context import GraphExecutionContext


def to_react_flow(context: GraphExecutionContext) -> dict:
    nodes = []
    edges = []
    for idx, node in enumerate(context.nodes.values()):
        nodes.append(
            {
                "id": node.id,
                "position": {"x": 100 + (idx % 3) * 280, "y": 80 + (idx // 3) * 160},
                "data": {
                    "label": node.agent,
                    "description": node.description,
                    "status": node.status,
                    "reads": node.reads,
                    "writes": node.writes,
                    "output": node.output or {},
                    "error": node.error,
                    "retries": node.retries,
                },
                "type": "agentNode",
            }
        )
    for source, target in context.edges:
        edges.append({"id": f"e-{source}-{target}", "source": source, "target": target, "type": "custom"})
    return {"nodes": nodes, "edges": edges}
