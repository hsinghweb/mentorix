from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from app.agents.adaptation import AdaptationAgent
from app.agents.assessment import AssessmentAgent
from app.agents.content import ContentGenerationAgent
from app.agents.learner_profile import LearnerProfilingAgent
from app.agents.planner import CurriculumPlannerAgent
from app.agents.reflection import ReflectionAgent
from app.core.event_bus import event_bus
from app.core.logging import DOMAIN_SCHEDULING, get_domain_logger
from app.core.query_optimizer import query_optimizer
from app.core.resilience import retry_with_backoff
from app.core.settings import settings
from app.memory.episodic import episodic_memory
from app.runtime.graph_context import GraphExecutionContext, RuntimeNode

logger = get_domain_logger(__name__, DOMAIN_SCHEDULING)


class RuntimeRunManager:
    def __init__(self):
        self._contexts: dict[str, GraphExecutionContext] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._run_dir = Path(settings.runtime_data_dir) / "runs"
        self.profile_agent = LearnerProfilingAgent()
        self.planner_agent = CurriculumPlannerAgent()
        self.content_agent = ContentGenerationAgent()
        self.assessment_agent = AssessmentAgent()
        self.adaptation_agent = AdaptationAgent()
        self.reflection_agent = ReflectionAgent()

    def _build_initial_graph(self, query: str) -> GraphExecutionContext:
        nodes = [
            RuntimeNode("N01", "QueryOptimizer", "Rewrite user query", reads=["query"], writes=["optimized_query"]),
            RuntimeNode("N02", "LearnerProfilingAgent", "Build baseline mastery", reads=[], writes=["mastery_map"]),
            RuntimeNode("N03", "CurriculumPlannerAgent", "Select concept/difficulty", reads=["mastery_map"], writes=["next_concept", "target_difficulty"]),
            RuntimeNode(
                "N04",
                "ContentGenerationAgent",
                "Generate grounded content",
                reads=["next_concept", "target_difficulty"],
                writes=["explanation"],
            ),
            RuntimeNode("N05", "AssessmentAgent", "Generate diagnostic", reads=["next_concept", "target_difficulty"], writes=["generated_question"]),
            RuntimeNode("N06", "ReflectionAgent", "Reflect and summarize", reads=["next_concept"], writes=["run_summary"]),
        ]
        edges = [("N01", "N02"), ("N02", "N03"), ("N03", "N04"), ("N03", "N05"), ("N05", "N06")]
        return GraphExecutionContext(query=query, nodes=nodes, edges=edges)

    async def start_run(self, query: str) -> str:
        context = self._build_initial_graph(query)
        self._contexts[context.run_id] = context
        await event_bus.publish("run_started", "run_manager", {"run_id": context.run_id, "query": query})
        task = asyncio.create_task(self._execute(context))
        self._tasks[context.run_id] = task
        return context.run_id

    async def stop_run(self, run_id: str) -> bool:
        context = self._contexts.get(run_id)
        if not context:
            return False
        context.stop_requested = True
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
        for node in context.nodes.values():
            if node.status in {"pending", "running"}:
                node.status = "stopped"
        context.status = "stopped"
        context.save(self._run_dir)
        await event_bus.publish("run_stopped", "run_manager", {"run_id": run_id})
        return True

    def get_context(self, run_id: str) -> GraphExecutionContext | None:
        return self._contexts.get(run_id)

    def list_runs(self) -> list[dict]:
        return [
            {"run_id": ctx.run_id, "status": ctx.status, "created_at": ctx.created_at, "updated_at": ctx.updated_at}
            for ctx in self._contexts.values()
        ]

    async def _execute(self, context: GraphExecutionContext) -> None:
        try:
            while not context.stop_requested and not context.all_done():
                ready = context.ready_steps()
                if not ready:
                    await asyncio.sleep(0.1)
                    continue
                for node_id in ready:
                    context.mark_running(node_id)
                    await event_bus.publish("step_start", "run_manager", {"run_id": context.run_id, "step_id": node_id})
                    await self._execute_step(context, node_id)
                    context.save(self._run_dir)

            if context.stop_requested:
                context.status = "stopped"
            elif any(n.status == "failed" for n in context.nodes.values()):
                context.status = "failed"
            else:
                context.status = "completed"
            context.save(self._run_dir)
            episodic_memory.save_episode(context.to_dict())
            await event_bus.publish("run_finished", "run_manager", {"run_id": context.run_id, "status": context.status})
        except Exception as exc:
            logger.exception("Run execution failed")
            context.status = "failed"
            context.metadata["error"] = str(exc)
            context.save(self._run_dir)
            await event_bus.publish("run_failed", "run_manager", {"run_id": context.run_id, "error": str(exc)})

    async def _execute_step(self, context: GraphExecutionContext, node_id: str) -> None:
        node = context.nodes[node_id]
        inputs = context.inputs_for(node_id)
        try:
            async def _call():
                return await self._dispatch(node.agent, context.query, inputs)

            output = await retry_with_backoff(_call)
            context.mark_done(node_id, output)
            await event_bus.publish(
                "step_success",
                "run_manager",
                {"run_id": context.run_id, "step_id": node_id, "agent": node.agent},
            )

            # Adaptive re-planning hook for ambiguous requests.
            if node.agent == "QueryOptimizer":
                optimized = str(output.get("optimized_query", ""))
                if optimized == context.query and len(context.query.split()) < 3:
                    inject = RuntimeNode(
                        id="N00",
                        agent="ClarificationAgent",
                        description="Clarify ambiguous query",
                        reads=["query"],
                        writes=["clarified_query"],
                    )
                    if "N00" not in context.nodes:
                        context.nodes["N00"] = inject
                        context.edges.append(("N00", "N02"))
                        context.globals_schema["clarified_query"] = f"Please clarify: {context.query}"
                        inject.status = "completed"
                        inject.output = {"clarified_query": context.globals_schema["clarified_query"]}
                        await event_bus.publish(
                            "run_replanned",
                            "run_manager",
                            {"run_id": context.run_id, "reason": "ambiguous_query"},
                        )
        except Exception as exc:
            node.retries += 1
            context.mark_failed(node_id, str(exc))
            await event_bus.publish(
                "step_failed",
                "run_manager",
                {"run_id": context.run_id, "step_id": node_id, "error": str(exc)},
            )

    async def _dispatch(self, agent_name: str, query: str, inputs: dict) -> dict:
        if agent_name == "QueryOptimizer":
            result = await query_optimizer.optimize_query(query)
            return {"optimized_query": result["optimized"], "changes_made": result["reasoning"]}

        if agent_name == "LearnerProfilingAgent":
            return await self.profile_agent.run({"mastery_map": {"fractions": 0.45, "linear_equations": 0.35}})

        if agent_name == "CurriculumPlannerAgent":
            return await self.planner_agent.run(
                {
                    "mastery_map": inputs.get("mastery_map") or {"fractions": 0.45, "linear_equations": 0.35},
                    "recent_concepts": [],
                }
            )

        if agent_name == "ContentGenerationAgent":
            concept = inputs.get("next_concept", "fractions")
            difficulty = int(inputs.get("target_difficulty", 1))
            return await self.content_agent.run(
                {"concept": concept, "difficulty": difficulty, "retrieved_chunks": [f"Curriculum chunk for {concept}"]}
            )

        if agent_name == "AssessmentAgent":
            concept = inputs.get("next_concept", "fractions")
            difficulty = int(inputs.get("target_difficulty", 1))
            return await self.assessment_agent.run({"concept": concept, "difficulty": difficulty})

        if agent_name == "ReflectionAgent":
            concept = str(inputs.get("next_concept", "fractions"))
            reflected = await self.reflection_agent.run(
                {"concept": concept, "current_score": 0.8, "mastery_map": {concept: 0.4}, "engagement_score": 0.5}
            )
            return {"run_summary": json.dumps(reflected), **reflected}

        return {"status": "noop"}


run_manager = RuntimeRunManager()
