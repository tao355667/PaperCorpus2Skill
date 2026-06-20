from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class BaseLLMProvider(Protocol):
    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        ...


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    base_url: str | None = None
    api_key: str | None = None
    api_key_env: str | None = None
    temperature: float = 0.2

    @property
    def resolved_api_key(self) -> str | None:
        if self.api_key:
            return self.api_key
        if self.api_key_env:
            return os.getenv(self.api_key_env)
        return None


class ProviderConfigurationError(RuntimeError):
    pass


class OpenAICompatibleProvider:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        api_key = self.config.resolved_api_key
        if not api_key:
            raise ProviderConfigurationError("OpenAI-compatible provider requires an API key.")
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
        }
        data = _post_json(
            f"{self.base_url}/chat/completions",
            payload,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        return data["choices"][0]["message"]["content"]


class AnthropicProvider:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.base_url = (config.base_url or "https://api.anthropic.com").rstrip("/")

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        api_key = self.config.resolved_api_key
        if not api_key:
            raise ProviderConfigurationError("Anthropic provider requires an API key.")
        system = "\n\n".join(message["content"] for message in messages if message["role"] == "system")
        user_messages = [message for message in messages if message["role"] != "system"]
        payload = {
            "model": self.config.model,
            "max_tokens": 4096,
            "temperature": temperature,
            "system": system,
            "messages": user_messages,
        }
        data = _post_json(
            f"{self.base_url}/v1/messages",
            payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        return "".join(part.get("text", "") for part in data.get("content", []))


class OllamaProvider:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.base_url = (config.base_url or "http://localhost:11434").rstrip("/")

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        data = _post_json(f"{self.base_url}/api/chat", payload, headers={})
        return data["message"]["content"]


def create_provider(config: LLMConfig) -> BaseLLMProvider:
    provider = config.provider.lower().replace("-", "_")
    if provider in {"openai", "openai_compatible"}:
        return OpenAICompatibleProvider(config)
    if provider == "anthropic":
        return AnthropicProvider(config)
    if provider == "ollama":
        return OllamaProvider(config)
    raise ProviderConfigurationError(f"Unsupported LLM provider: {config.provider}")


def _post_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM request failed with HTTP {exc.code}: {body}") from exc
