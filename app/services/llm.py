from __future__ import annotations

import ipaddress
import json
import os
import socket
from typing import Any
from urllib.parse import urlparse

import httpx


def request_llm(provider: str | None = None, model: str | None = None, api_key: str | None = None, base_url: str | None = None, timeout: float = 30.0) -> "LLMProvider":
    """Build a request-scoped provider; absent values fall back to server defaults."""
    return LLMProvider(provider=provider or None, model=model or None, api_key=api_key or None, base_url=base_url or None, timeout=timeout)


class ProviderError(RuntimeError):
    """Raised when a configured model provider cannot return a valid response."""


_OFFICIAL_PROVIDER_HOSTS = {
    "openai": "api.openai.com",
    "anthropic": "api.anthropic.com",
    "mistral": "api.mistral.ai",
    "gemini": "generativelanguage.googleapis.com",
}


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
        self.model = model if model is not None else os.getenv("DIS_LLM_MODEL", "")
        configured_base_url = base_url if base_url is not None else os.getenv("DIS_LLM_BASE_URL", "")
        if not configured_base_url:
            configured_base_url = {
                "mistral": "https://api.mistral.ai/v1",
                "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
            }.get(self.provider, "")
        self.base_url = configured_base_url.rstrip("/")
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.model)

    def _validate_provider_endpoint(self) -> None:
        """Prevent a known provider profile from silently targeting another provider."""
        host = (urlparse(self.base_url).hostname or "").lower() if self.base_url else ""
        if not host:
            return
        for provider, official_host in _OFFICIAL_PROVIDER_HOSTS.items():
            if host == official_host and self.provider != provider:
                raise ProviderError(
                    f"The selected {self.provider} provider is configured with the {provider} API endpoint. "
                    "Correct the Custom API base URL in Settings or restore this provider's default endpoint."
                )

    def _validate_custom_base_url(self) -> None:
        if not self.base_url:
            return
        parsed = urlparse(self.base_url)
        host = (parsed.hostname or "").rstrip(".").lower()
        if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ProviderError("Custom model endpoints must use HTTPS and must not contain credentials, query strings, or fragments.")
        if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local")):
            raise ProviderError("Local and private model endpoints are not allowed.")
        try:
            addresses = {ipaddress.ip_address(host)}
        except ValueError:
            try:
                addresses = {
                    ipaddress.ip_address(item[4][0])
                    for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
                }
            except (OSError, ValueError) as exc:
                raise ProviderError("Custom model endpoint hostname could not be resolved safely.") from exc
        if not addresses or any(not address.is_global for address in addresses):
            raise ProviderError("Custom model endpoints must resolve only to public IP addresses.")

    def complete_json(self, system: str, prompt: str, max_tokens: int = 1800) -> dict[str, Any]:
        if not self.enabled:
            raise ProviderError("LLM provider is not configured")
        try:
            if self.provider == "anthropic":
                content = self._anthropic(system, prompt, max_tokens=max_tokens)
            elif self.provider in {"openai", "openai-compatible", "groq", "gemini", "mistral", "openrouter"}:
                content = self._openai_compatible(system, prompt, max_tokens=max_tokens)
            else:
                raise ProviderError(f"Unsupported provider: {self.provider}")
            parsed = self._parse_json(content)
            if not isinstance(parsed, dict):
                raise ProviderError("Model response must be a JSON object")
            return parsed
        except ProviderError:
            raise
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = self._provider_http_error_detail(exc.response)
            suffix = f": {detail}" if detail else ""
            raise ProviderError(f"Model provider rejected the request (HTTP {status}){suffix}") from exc
        except httpx.TimeoutException as exc:
            raise ProviderError("Model provider request timed out. Check provider availability and try again.") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("Could not connect to the model provider. Check the API endpoint and network access.") from exc
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Model provider returned an invalid or unexpected response. Check the provider/model compatibility.") from exc

    def _provider_http_error_detail(self, response: httpx.Response) -> str:
        """Return a short, credential-redacted provider error without exposing response payloads."""
        try:
            payload = response.json()
        except ValueError:
            return ""
        if not isinstance(payload, dict):
            return ""
        error = payload.get("error", payload)
        if not isinstance(error, dict):
            return ""
        message = error.get("message") or error.get("detail") or error.get("status")
        if not isinstance(message, str):
            return ""
        message = message.replace(self.api_key, "[REDACTED]") if self.api_key else message
        message = " ".join(message.split())
        return message[:300]

    def _openai_compatible(self, system: str, prompt: str, max_tokens: int = 1800) -> str:
        self._validate_custom_base_url()
        base = self.base_url or "https://api.openai.com/v1"
        response = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "temperature": 0.2,
                "max_tokens": max(256, min(max_tokens, 16000)),
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

    def _anthropic(self, system: str, prompt: str, max_tokens: int = 1800) -> str:
        self._validate_custom_base_url()
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
                "max_tokens": max(256, min(max_tokens, 16000)),
                "temperature": 0.2,
                "system": system + " Return only a valid JSON object, with no markdown fences.",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]


    def analyze_images_json(
        self, system: str, prompt: str, images: list[dict[str, str]]
    ) -> dict[str, Any]:
        """Analyze bounded base64 image inputs and return a validated JSON object."""
        if not self.enabled:
            raise ProviderError("LLM provider is not configured")
        if not images or len(images) > 6:
            raise ProviderError("Image analysis requires between one and six images")
        normalized = []
        for item in images:
            data = item.get("data", "")
            media_type = item.get("media_type", "image/jpeg")
            if media_type not in {"image/jpeg", "image/png", "image/webp"}:
                raise ProviderError("Unsupported image media type")
            if not data or len(data) > 2_500_000:
                raise ProviderError("Image data is empty or exceeds the size limit")
            normalized.append({"data": data, "media_type": media_type})
        try:
            if self.provider == "anthropic":
                content = self._anthropic_images(system, prompt, normalized)
            elif self.provider in {"openai", "openai-compatible", "groq", "gemini", "mistral", "openrouter"}:
                content = self._openai_compatible_images(system, prompt, normalized)
            else:
                raise ProviderError(f"Unsupported provider: {self.provider}")
            parsed = self._parse_json(content)
            if not isinstance(parsed, dict):
                raise ProviderError("Model response must be a JSON object")
            return parsed
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Vision provider request failed or returned an invalid response") from exc

    def _openai_compatible_images(
        self, system: str, prompt: str, images: list[dict[str, str]]
    ) -> str:
        self._validate_custom_base_url()
        base = self.base_url or "https://api.openai.com/v1"
        content = [{"type": "text", "text": prompt}]
        content.extend({
            "type": "image_url",
            "image_url": {"url": f"data:{item['media_type']};base64,{item['data']}", "detail": "high"},
        } for item in images)
        response = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": content},
                ],
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]["content"]
        if isinstance(message, list):
            return "".join(part.get("text", "") for part in message if isinstance(part, dict))
        if not isinstance(message, str):
            raise ProviderError("Vision provider returned no text content")
        return message

    def _anthropic_images(
        self, system: str, prompt: str, images: list[dict[str, str]]
    ) -> str:
        self._validate_custom_base_url()
        base = self.base_url or "https://api.anthropic.com/v1"
        content = [{"type": "text", "text": prompt}]
        content.extend({
            "type": "image",
            "source": {"type": "base64", "media_type": item["media_type"], "data": item["data"]},
        } for item in images)
        response = httpx.post(
            f"{base}/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 2400,
                "temperature": 0.2,
                "system": system + " Return only a valid JSON object, with no markdown fences.",
                "messages": [{"role": "user", "content": content}],
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return "".join(
            item.get("text", "") for item in response.json()["content"]
            if isinstance(item, dict) and item.get("type") == "text"
        )

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
