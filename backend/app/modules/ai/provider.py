"""LLM provider gateway — the only place vendor SDK/HTTP details may live.

Config-selected: `echo` is a deterministic local provider (development, CI,
and a graceful degraded mode); `anthropic` is the production implementation.
Adding a vendor = one class + one registry entry; the service layer, prompts,
queueing, and caching never change.
"""
import time
from typing import Protocol

import httpx
from pydantic import BaseModel

from app.core.config import get_settings


class AICompletion(BaseModel):
    content: str
    provider: str
    model: str
    tokens_input: int = 0
    tokens_output: int = 0
    latency_ms: int = 0


class AIProvider(Protocol):
    name: str

    async def complete(self, prompt: str) -> AICompletion: ...


class EchoProvider:
    """Deterministic stand-in: returns a bounded echo of the prompt. Keeps the
    entire pipeline (queueing, persistence, caching, events) exercisable with
    no network and no keys."""

    name = "echo"

    async def complete(self, prompt: str) -> AICompletion:
        settings = get_settings()
        return AICompletion(
            content=f"[echo:{settings.ai_model}] {prompt[:800]}",
            provider=self.name,
            model=settings.ai_model,
            tokens_input=len(prompt.split()),
            tokens_output=min(len(prompt.split()), 200),
            latency_ms=0,
        )


class AnthropicProvider:
    name = "anthropic"
    _endpoint = "https://api.anthropic.com/v1/messages"

    async def complete(self, prompt: str) -> AICompletion:
        settings = get_settings()
        started = time.monotonic()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                self._endpoint,
                headers={
                    "x-api-key": settings.ai_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.ai_model,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        if resp.status_code != 200:
            raise RuntimeError(f"AI provider error {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        content = "".join(
            block.get("text", "") for block in data.get("content", [])
            if block.get("type") == "text"
        )
        usage = data.get("usage", {})
        return AICompletion(
            content=content,
            provider=self.name,
            model=data.get("model", settings.ai_model),
            tokens_input=int(usage.get("input_tokens", 0)),
            tokens_output=int(usage.get("output_tokens", 0)),
            latency_ms=int((time.monotonic() - started) * 1000),
        )


def get_provider() -> AIProvider:
    settings = get_settings()
    providers: dict[str, AIProvider] = {
        "echo": EchoProvider(),
        "anthropic": AnthropicProvider(),
    }
    return providers[settings.ai_provider]
