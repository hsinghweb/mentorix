import json
from abc import ABC, abstractmethod
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.core.settings import settings


def _estimate_tokens(text: str) -> int:
    # Lightweight deterministic estimate used for observability without provider-specific token APIs.
    return max(1, len((text or "").strip()) // 4)


class BaseLLMProvider(ABC):
    provider_name: str

    @abstractmethod
    async def generate(self, prompt: str) -> tuple[str | None, dict]:
        raise NotImplementedError


class GeminiLLMProvider(BaseLLMProvider):
    provider_name = "gemini"

    @staticmethod
    def _sanitize_url(raw_url: str) -> str:
        parsed = urlparse(raw_url)
        if not parsed.query:
            return raw_url
        filtered = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() != "key"]
        return urlunparse(parsed._replace(query=urlencode(filtered)))

    async def generate(self, prompt: str) -> tuple[str | None, dict]:
        if not settings.gemini_api_key:
            return None, {"provider": self.provider_name, "model": settings.llm_model, "reason": "missing_api_key"}

        api_url = settings.gemini_api_url.strip()
        if not api_url:
            api_url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{settings.llm_model}:generateContent"
            )
        api_url = self._sanitize_url(api_url)

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 700},
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                api_url,
                json=payload,
                headers={"x-goog-api-key": settings.gemini_api_key},
            )
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return None, {"provider": self.provider_name, "model": settings.llm_model, "reason": "no_candidates"}
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "\n".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            usage = {
                "provider": self.provider_name,
                "model": settings.llm_model,
                "prompt_tokens_estimate": _estimate_tokens(prompt),
                "completion_tokens_estimate": _estimate_tokens(text),
                "total_tokens_estimate": _estimate_tokens(prompt) + _estimate_tokens(text),
            }
            return (text or None), usage


class NullLLMProvider(BaseLLMProvider):
    provider_name = "none"

    async def generate(self, prompt: str) -> tuple[str | None, dict]:
        return None, {
            "provider": self.provider_name,
            "model": "none",
            "prompt_tokens_estimate": _estimate_tokens(prompt),
            "completion_tokens_estimate": 0,
            "total_tokens_estimate": _estimate_tokens(prompt),
            "reason": "unsupported_provider",
        }


def get_llm_provider() -> BaseLLMProvider:
    provider = (settings.llm_provider or "").lower()
    if provider == "gemini":
        return GeminiLLMProvider()
    return NullLLMProvider()
