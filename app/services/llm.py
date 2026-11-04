from __future__ import annotations

import json
import os
from typing import Any

import httpx


class ProviderError(RuntimeError):
    """Raised when a configured model provider cannot return a valid response."""


class LLMProvider:
    """Small synchronous provider adapter for OpenAI-compatible and Anthropic APIs.

    The provider is opt-in. With no DIS_LLM_API_KEY, DIS remains deterministic and
    does not make network calls. Credentials are read from the environment only.
    """

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.provider = (provider or os.getenv("DIS_LLM_PROVIDER", "openai")).lower()
        self.api_key = api_key if api_key is not None else os.getenv("DIS_LLM_API_KEY", "")
        self.model = model or os.getenv("DIS_LLM_MODEL", "")
        self.base_url = (base_url or os.getenv("DIS_LLM_BASE_URL", "")).rstrip("/")
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.model)

    def complete_json(self, system: str, prompt: str) -> dict[str, Any]:
        if not self.enabled:
            raise ProviderError("LLM provider is not configured")
        try:
            if self.provider == "anthropic":
                content = self._anthropic(system, prompt)
            elif self.provider in {"openai", "openai-compatible", "groq", "gemini", "mistral", "openrouter"}:
                content = self._openai_compatible(system, prompt)
            else:
                raise ProviderError(f"Unsupported provider: {self.provider}")
            parsed = self._parse_json(content)
            if not isinstance(parsed, dict):
                raise ProviderError("Model response must be a JSON object")
            return parsed
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Model provider request failed or returned an invalid response") from exc

    def _openai_compatible(self, system: str, prompt: str) -> str:
        base = self.base_url or "https://api.openai.com/v1"
        response = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _anthropic(self, system: str, prompt: str) -> str:
        base = self.base_url or "https://api.anthropic.com/v1"
        response = httpx.post(
            f"{base}/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 1800,
                "temperature": 0.2,
                "system": system + " Return only a valid JSON object, with no markdown fences.",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderError("Model response was not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ProviderError("Model response must be a JSON object")
        return parsed
