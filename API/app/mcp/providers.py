from __future__ import annotations

from app.core.llm_provider import get_llm_provider
from app.mcp.contracts import MCPRequest
from app.mcp.server import mcp_server


async def _provider_llm_generate_text(request: MCPRequest) -> dict:
    prompt = str(request.payload.get("prompt") or "")
    role = str(request.payload.get("role") or "content_generator")
    if not prompt.strip():
        raise ValueError("payload.prompt is required")
    provider = get_llm_provider(role=role)
    text, meta = await provider.generate(prompt)
    if not text:
        raise RuntimeError("LLM provider returned empty output")
    return {
        "text": text,
        "meta": meta if isinstance(meta, dict) else {},
        "role": role,
    }


async def _provider_recommend_timeline(request: MCPRequest) -> dict:
    selected = int(request.payload.get("selected_timeline_weeks") or 14)
    score = float(request.payload.get("score") or 0.0)
    selected = max(14, min(28, selected))
    if score >= 0.85:
        return {
            "recommended_timeline_weeks": max(14, selected - 1),
            "timeline_recommendation_note": (
                "Strong diagnostic performance. You can target a slightly faster completion plan."
            ),
        }
    if score >= 0.70:
        return {
            "recommended_timeline_weeks": selected,
            "timeline_recommendation_note": "Good baseline. Your selected timeline looks realistic.",
        }
    if score >= 0.55:
        return {
            "recommended_timeline_weeks": min(28, selected + 2),
            "timeline_recommendation_note": (
                "Moderate baseline. A slightly extended timeline should improve retention."
            ),
        }
    if score >= 0.40:
        return {
            "recommended_timeline_weeks": min(28, selected + 4),
            "timeline_recommendation_note": (
                "Foundation needs reinforcement. A longer timeline is recommended for confidence."
            ),
        }
    return {
        "recommended_timeline_weeks": min(28, selected + 6),
        "timeline_recommendation_note": (
            "Strongly recommended to extend timeline and focus on fundamentals first."
        ),
    }


def register_default_mcp_providers() -> None:
    if not mcp_server.has_provider("llm.generate_text"):
        mcp_server.register("llm.generate_text", _provider_llm_generate_text)
    if not mcp_server.has_provider("onboarding.recommend_timeline"):
        mcp_server.register("onboarding.recommend_timeline", _provider_recommend_timeline)
