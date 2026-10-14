"""LLM clients behind one small interface, plus token cost accounting.

Clients are injectable (same approach as clinical-notes-eval): the test suite
uses `FakeClient`, so it needs no network and no API key. Network and API
errors propagate: a broken run must never be scored as a wrong answer.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

import yaml

from . import config


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0


@lru_cache(maxsize=1)
def _pricing() -> dict:
    return yaml.safe_load((config.ROOT / "config" / "pricing.yaml").read_text())["models"]


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = _pricing().get(model)
    if prices is None:
        prices = _pricing()["local"] if ":" in model else None  # ollama tags look like qwen2.5:7b
    if prices is None:
        return float("nan")  # unknown model: visible in reports rather than silently 0
    return round((input_tokens * prices["input"] + output_tokens * prices["output"]) / 1e6, 8)


def estimate_tokens(text: str) -> int:
    """Rough estimate (4 characters per token) used when a backend reports no usage."""
    return max(1, len(text) // 4)


class AnthropicClient:
    def __init__(self, model: str | None = None, client=None, max_tokens: int = 500):
        self.model = model or config.DEFAULT_MODEL
        self._client = client
        self.max_tokens = max_tokens

    @property
    def client(self):
        if self._client is None:
            import anthropic  # lazy: the offline path needs no SDK

            self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        return self._client

    def complete(self, system: str, user: str) -> Completion:
        t0 = time.perf_counter()
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "text") == "text")
        usage = getattr(resp, "usage", None)
        return Completion(
            text=text,
            model=self.model,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        )


def _http_post(url: str, headers: dict, payload: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class OpenAICompatClient:
    """Any OpenAI-compatible chat endpoint, e.g. a local model served by Ollama."""

    def __init__(self, model: str, base_url: str = "http://localhost:11434/v1", api_key: str | None = None,
                 post: Callable[[str, dict, dict], dict] | None = None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("CCP_API_KEY")
        self._post = post or _http_post

    def complete(self, system: str, user: str) -> Completion:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"model": self.model, "temperature": 0,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        t0 = time.perf_counter()
        data = self._post(f"{self.base_url}/chat/completions", headers, payload)
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"unexpected response from {self.base_url}: {str(data)[:200]}")
        usage = data.get("usage") or {}
        return Completion(
            text=text,
            model=self.model,
            input_tokens=usage.get("prompt_tokens") or estimate_tokens(system + user),
            output_tokens=usage.get("completion_tokens") or estimate_tokens(text),
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        )


class FakeClient:
    """Test double: returns canned replies, or computes them from the prompt."""

    def __init__(self, replies: list[str] | Callable[[str, str], str], model: str = "fake"):
        self._replies = replies
        self.model = model
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> Completion:
        self.calls.append((system, user))
        if callable(self._replies):
            text = self._replies(system, user)
        else:
            text = self._replies[min(len(self.calls), len(self._replies)) - 1]
        return Completion(text, self.model, estimate_tokens(system + user), estimate_tokens(text), 1.0)


def make_client(kind: str, model: str | None = None, base_url: str | None = None):
    if kind == "anthropic":
        return AnthropicClient(model)
    if kind == "openai-compat":
        if not model:
            raise ValueError("--model is required for openai-compat")
        return OpenAICompatClient(model, base_url or "http://localhost:11434/v1")
    raise ValueError(f"unknown client kind {kind!r}")
