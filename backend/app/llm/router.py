from __future__ import annotations

import logging
from typing import Literal

from langchain_core.language_models import BaseChatModel

from app.config import settings

logger = logging.getLogger(__name__)

ProviderType = Literal["ollama", "openai", "anthropic"]


def get_ollama_llm(model: str | None = None) -> BaseChatModel:
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=model or settings.default_model_name,
        base_url=settings.ollama_base_url,
    )


def get_openai_llm(model: str = "gpt-4o") -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=settings.openai_api_key,
    )


def get_anthropic_llm(model: str = "claude-sonnet-4-20250514") -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=model,
        api_key=settings.anthropic_api_key,
    )


_PROVIDER_FACTORIES = {
    "ollama": get_ollama_llm,
    "openai": get_openai_llm,
    "anthropic": get_anthropic_llm,
}


class LLMRouter:
    """Routes LLM calls to the configured provider with fallback support."""

    def __init__(
        self,
        primary: ProviderType | None = None,
        fallback: ProviderType | None = None,
        model: str | None = None,
    ) -> None:
        self.primary = primary or settings.default_llm_provider
        self.fallback = fallback
        self.model = model
        self._cache: dict[str, BaseChatModel] = {}

    def get_llm(self, provider: ProviderType | None = None, model: str | None = None) -> BaseChatModel:
        provider = provider or self.primary
        model = model or self.model
        cache_key = f"{provider}:{model}"

        if cache_key not in self._cache:
            factory = _PROVIDER_FACTORIES.get(provider)
            if not factory:
                raise ValueError(f"Unknown LLM provider: {provider}")
            kwargs = {"model": model} if model else {}
            self._cache[cache_key] = factory(**kwargs)
            logger.info("Initialized LLM: provider=%s model=%s", provider, model)

        return self._cache[cache_key]

    async def invoke_with_fallback(self, messages: list, **kwargs) -> str:
        """Try primary provider, fall back if it fails."""
        try:
            llm = self.get_llm(self.primary, self.model)
            result = await llm.ainvoke(messages, **kwargs)
            return result.content
        except Exception as e:
            if self.fallback:
                logger.warning("Primary LLM failed (%s), falling back to %s", e, self.fallback)
                llm = self.get_llm(self.fallback)
                result = await llm.ainvoke(messages, **kwargs)
                return result.content
            raise


llm_router = LLMRouter()
