"""LLM provider adapters with OpenAI/Anthropic support and automatic fallback."""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

import anthropic
from loguru import logger
from openai import AsyncOpenAI

from src.config import get_settings

settings = get_settings()


class LLMResponse:
    def __init__(
        self,
        content: str,
        tokens_used: int,
        provider: str,
        model: str,
        raw: Any = None,
    ) -> None:
        self.content = content
        self.tokens_used = tokens_used
        self.provider = provider
        self.model = model
        self.raw = raw

    def parse_json(self) -> dict[str, Any]:
        """Extract JSON from the LLM response, handling markdown code blocks."""
        text = self.content.strip()
        # Try to extract from code block
        pattern = r"```(?:json)?\s*([\s\S]*?)```"
        match = re.search(pattern, text)
        if match:
            text = match.group(1).strip()
        # Try to find JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]
        return json.loads(text)


class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self._client: Optional[AsyncOpenAI] = None
        self._api_key = api_key

    def is_available(self) -> bool:
        return bool(self._api_key and self._api_key.startswith("sk-"))

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def generate(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        client = self._get_client()
        final_messages: list[dict[str, str]] = []
        if system:
            final_messages.append({"role": "system", "content": system})
        final_messages.extend(messages)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": final_messages,
            "temperature": temperature if temperature is not None else settings.llm_temperature,
            "max_tokens": max_tokens or settings.llm_max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        return LLMResponse(
            content=content,
            tokens_used=tokens,
            provider="openai",
            model=self.model,
            raw=response,
        )


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self._api_key = api_key
        self._client: Optional[anthropic.AsyncAnthropic] = None

    def is_available(self) -> bool:
        return bool(self._api_key and self._api_key.startswith("sk-ant-"))

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def generate(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        client = self._get_client()

        anthropic_messages = []
        for msg in messages:
            anthropic_messages.append({"role": msg["role"], "content": msg["content"]})

        final_system = system or ""
        if json_mode and final_system:
            final_system += "\n\nYou must respond with valid JSON only. No markdown, no explanation outside the JSON object."
        elif json_mode:
            final_system = "You must respond with valid JSON only. No markdown, no explanation outside the JSON object."

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens or settings.llm_max_tokens,
            "temperature": temperature if temperature is not None else settings.llm_temperature,
        }
        if final_system:
            kwargs["system"] = final_system

        response = await client.messages.create(**kwargs)
        content = response.content[0].text if response.content else ""
        tokens = (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0
        return LLMResponse(
            content=content,
            tokens_used=tokens,
            provider="anthropic",
            model=self.model,
            raw=response,
        )


class FallbackLLMProvider:
    """Tries primary provider, falls back to secondary on failure."""

    def __init__(self) -> None:
        self._primary = self._build_provider(
            settings.llm_primary_provider,
            settings.llm_primary_model,
        )
        self._fallback = self._build_provider(
            settings.llm_fallback_provider,
            settings.llm_fallback_model,
        )

    def _build_provider(self, name: str, model: str) -> BaseLLMProvider:
        if name == "openai":
            return OpenAIProvider(api_key=settings.openai_api_key, model=model)
        elif name == "anthropic":
            return AnthropicProvider(api_key=settings.anthropic_api_key, model=model)
        raise ValueError(f"Unknown LLM provider: {name}")

    async def generate(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        if self._primary.is_available():
            try:
                t0 = time.monotonic()
                result = await self._primary.generate(
                    messages=messages,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                )
                logger.debug(f"LLM primary OK in {(time.monotonic()-t0)*1000:.0f}ms, tokens={result.tokens_used}")
                return result
            except Exception as exc:
                logger.warning(f"Primary LLM failed: {exc}, trying fallback")

        if self._fallback.is_available():
            try:
                t0 = time.monotonic()
                result = await self._fallback.generate(
                    messages=messages,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                )
                logger.debug(f"LLM fallback OK in {(time.monotonic()-t0)*1000:.0f}ms, tokens={result.tokens_used}")
                return result
            except Exception as exc:
                logger.error(f"Fallback LLM also failed: {exc}")
                raise

        raise RuntimeError(
            "No LLM providers available. Set OPENAI_API_KEY or ANTHROPIC_API_KEY."
        )

    async def simple_chat(self, user_message: str, system: Optional[str] = None) -> str:
        response = await self.generate(
            messages=[{"role": "user", "content": user_message}],
            system=system,
        )
        return response.content

    async def structured_response(
        self,
        user_message: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        response = await self.generate(
            messages=[{"role": "user", "content": user_message}],
            system=system,
            temperature=temperature,
            json_mode=True,
        )
        return response.parse_json()


_llm_provider: Optional[FallbackLLMProvider] = None


def get_llm_provider() -> FallbackLLMProvider:
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = FallbackLLMProvider()
    return _llm_provider
