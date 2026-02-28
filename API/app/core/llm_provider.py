from abc import ABC, abstractmethod
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.core.model_registry import resolve_role
from app.core.resilience import get_breaker, retry_with_backoff
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

    def __init__(self, model_name: str | None = None, role: str | None = None, cost_per_1k: float | None = None):
        self.model_name = model_name or settings.llm_model
        self.role = role or "content_generator"
        self.cost_per_1k = float(cost_per_1k or 0.0)

    @staticmethod
    def _sanitize_url(raw_url: str) -> str:
        parsed = urlparse(raw_url)
        if not parsed.query:
            return raw_url
        filtered = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() != "key"]
        return urlunparse(parsed._replace(query=urlencode(filtered)))

    async def generate(self, prompt: str) -> tuple[str | None, dict]:
        if not settings.gemini_api_key:
            return None, {"provider": self.provider_name, "model": self.model_name, "reason": "missing_api_key"}

        api_url = settings.gemini_api_url.strip()
        if not api_url:
            api_url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model_name}:generateContent"
            )
        api_url = self._sanitize_url(api_url)

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 700},
        }

        breaker = get_breaker(f"llm:{self.provider_name}:{self.model_name}:{self.role}")
        if not breaker.can_execute():
            return None, {"provider": self.provider_name, "model": self.model_name, "reason": "circuit_open"}

        async def _call():
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
                    return None, {
                        "provider": self.provider_name,
                        "model": self.model_name,
                        "reason": "no_candidates",
                    }
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "\n".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
                usage = {
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "role": self.role,
                    "prompt_tokens_estimate": _estimate_tokens(prompt),
                    "completion_tokens_estimate": _estimate_tokens(text),
                    "total_tokens_estimate": _estimate_tokens(prompt) + _estimate_tokens(text),
                    "cost_estimate_usd": round(((_estimate_tokens(prompt) + _estimate_tokens(text)) / 1000) * self.cost_per_1k, 6),
                }
                return (text or None), usage

        try:
            result = await retry_with_backoff(_call)
            breaker.record_success()
            return result
        except Exception as e:
            breaker.record_failure()
            resp = getattr(e, "response", None)
            status = getattr(resp, "status_code", None)
            err_msg = (str(e) or "").lower()
            # If model not available (404 / upgrade message), retry with flash
            use_fallback = (
                status == 404
                or "not available" in err_msg
                or "upgrade" in err_msg
                or "404" in err_msg
            )
            if use_fallback:
                fallback = "gemini-2.5-flash"
                if fallback != self.model_name:
                    self.model_name = fallback
                    api_url_fb = (
                        f"https://generativelanguage.googleapis.com/v1beta/models/"
                        f"{self.model_name}:generateContent"
                    )
                    try:
                        async with httpx.AsyncClient(timeout=20.0) as client:
                            response = await client.post(
                                api_url_fb,
                                json=payload,
                                headers={"x-goog-api-key": settings.gemini_api_key},
                            )
                            response.raise_for_status()
                            data = response.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                text = "\n".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
                                return (text or None), {
                                    "provider": self.provider_name,
                                    "model": self.model_name,
                                    "role": self.role,
                                    "fallback_used": True,
                                }
                    except Exception:
                        pass
            raise


class OllamaLLMProvider(BaseLLMProvider):
    provider_name = "ollama"

    def __init__(self, model_name: str, role: str | None = None, cost_per_1k: float | None = None):
        self.model_name = model_name
        self.role = role or "verifier"
        self.cost_per_1k = float(cost_per_1k or 0.0)

    async def generate(self, prompt: str) -> tuple[str | None, dict]:
        breaker = get_breaker(f"llm:{self.provider_name}:{self.model_name}:{self.role}")
        if not breaker.can_execute():
            return None, {"provider": self.provider_name, "model": self.model_name, "reason": "circuit_open"}

        async def _call():
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{settings.ollama_base_url.rstrip('/')}/api/generate",
                    json={"model": self.model_name, "prompt": prompt, "stream": False},
                )
                response.raise_for_status()
                body = response.json()
                text = (body.get("response") or "").strip()
                usage = {
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "role": self.role,
                    "prompt_tokens_estimate": _estimate_tokens(prompt),
                    "completion_tokens_estimate": _estimate_tokens(text),
                    "total_tokens_estimate": _estimate_tokens(prompt) + _estimate_tokens(text),
                    "cost_estimate_usd": round(((_estimate_tokens(prompt) + _estimate_tokens(text)) / 1000) * self.cost_per_1k, 6),
                }
                return (text or None), usage

        try:
            result = await retry_with_backoff(_call)
            breaker.record_success()
            return result
        except Exception:
            breaker.record_failure()
            raise


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


def get_llm_provider(role: str | None = None) -> BaseLLMProvider:
    if settings.role_model_governance_enabled:
        resolved = resolve_role(role)
        provider = (resolved.get("provider") or "").lower()
        model_name = resolved.get("model")
        cost_per_1k = float(resolved.get("cost_per_1k", 0.0) or 0.0)
        if provider == "gemini":
            return GeminiLLMProvider(model_name=model_name, role=role, cost_per_1k=cost_per_1k)
        if provider == "ollama":
            return OllamaLLMProvider(
                model_name=model_name or settings.ollama_model,
                role=role,
                cost_per_1k=cost_per_1k,
            )
        return NullLLMProvider()

    provider = (settings.llm_provider or "").lower()
    if provider == "gemini":
        return GeminiLLMProvider(model_name=settings.llm_model, role=role, cost_per_1k=0.0)
    if provider == "ollama":
        return OllamaLLMProvider(model_name=settings.ollama_model, role=role, cost_per_1k=0.0)
    return NullLLMProvider()
