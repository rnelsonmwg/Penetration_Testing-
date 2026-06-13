"""
Concrete AI provider implementations.

Grouped by wire protocol:
  * OllamaProvider          - local Ollama HTTP API (/api/chat)
  * ClaudeProvider          - Anthropic Messages API
  * OpenAICompatProvider    - shared base for the OpenAI chat-completions shape,
                              subclassed by OpenAI, Groq, DeepSeek, and Grok/xAI,
                              which all speak the same protocol on different hosts.
"""

from __future__ import annotations

from typing import Optional

import httpx

from .base import (
    AIProvider,
    ProviderConfig,
    ProviderError,
    ProviderResponse,
    available_providers,
    get_provider,
    register,
)


# --------------------------------------------------------------------------- #
# Ollama (local, free)
# --------------------------------------------------------------------------- #
@register
class OllamaProvider(AIProvider):
    name = "ollama"
    label = "Ollama (local)"
    local = True
    default_model = "llama3.1"

    def _base(self) -> str:
        import os

        return (
            self.config.base_url
            or os.getenv("OLLAMA_HOST")
            or "http://localhost:11434"
        ).rstrip("/")

    def is_available(self) -> bool:
        try:
            r = httpx.get(f"{self._base()}/api/tags", timeout=3.0)
            return r.status_code == 200
        except Exception:
            return False

    def complete(self, prompt: str, system: Optional[str] = None) -> ProviderResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.config.temperature},
        }
        try:
            r = httpx.post(
                f"{self._base()}/api/chat",
                json=payload,
                timeout=self.config.timeout,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:  # pragma: no cover - network
            raise ProviderError(f"Ollama request failed: {e}") from e
        text = (data.get("message") or {}).get("content", "")
        return ProviderResponse(text=text, model=self.config.model, provider=self.name, raw=data)


# --------------------------------------------------------------------------- #
# Claude (Anthropic Messages API)
# --------------------------------------------------------------------------- #
@register
class ClaudeProvider(AIProvider):
    name = "claude"
    label = "Claude (Anthropic)"
    local = False
    default_model = "claude-sonnet-4-6"

    def _base(self) -> str:
        return (self.config.base_url or "https://api.anthropic.com").rstrip("/")

    def is_available(self) -> bool:
        return bool(self.config.api_key)

    def complete(self, prompt: str, system: Optional[str] = None) -> ProviderResponse:
        if not self.config.api_key:
            raise ProviderError("Claude requires an API key (ANTHROPIC_API_KEY).")
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        try:
            r = httpx.post(
                f"{self._base()}/v1/messages",
                json=payload,
                headers=headers,
                timeout=self.config.timeout,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:  # pragma: no cover - network
            raise ProviderError(f"Claude request failed: {e}") from e
        parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
        return ProviderResponse(
            text="".join(parts), model=self.config.model, provider=self.name, raw=data
        )


# --------------------------------------------------------------------------- #
# OpenAI-compatible family
# --------------------------------------------------------------------------- #
class OpenAICompatProvider(AIProvider):
    """Base for any backend speaking the OpenAI /chat/completions protocol."""

    api_base_default = "https://api.openai.com/v1"
    env_hint = "OPENAI_API_KEY"

    def _base(self) -> str:
        return (self.config.base_url or self.api_base_default).rstrip("/")

    def is_available(self) -> bool:
        return bool(self.config.api_key)

    def complete(self, prompt: str, system: Optional[str] = None) -> ProviderResponse:
        if not self.config.api_key:
            raise ProviderError(f"{self.label} requires an API key ({self.env_hint}).")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        try:
            r = httpx.post(
                f"{self._base()}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.config.timeout,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:  # pragma: no cover - network
            raise ProviderError(f"{self.label} request failed: {e}") from e
        text = data["choices"][0]["message"]["content"]
        return ProviderResponse(
            text=text, model=self.config.model, provider=self.name, raw=data
        )


@register
class OpenAIProvider(OpenAICompatProvider):
    name = "openai"
    label = "OpenAI"
    default_model = "gpt-4o-mini"
    api_base_default = "https://api.openai.com/v1"
    env_hint = "OPENAI_API_KEY"


@register
class GroqProvider(OpenAICompatProvider):
    name = "groq"
    label = "Groq"
    default_model = "llama-3.3-70b-versatile"
    api_base_default = "https://api.groq.com/openai/v1"
    env_hint = "GROQ_API_KEY"


@register
class DeepSeekProvider(OpenAICompatProvider):
    name = "deepseek"
    label = "DeepSeek"
    default_model = "deepseek-chat"
    api_base_default = "https://api.deepseek.com/v1"
    env_hint = "DEEPSEEK_API_KEY"


@register
class GrokProvider(OpenAICompatProvider):
    name = "grok"
    label = "Grok / xAI"
    default_model = "grok-2-latest"
    api_base_default = "https://api.x.ai/v1"
    env_hint = "XAI_API_KEY"
