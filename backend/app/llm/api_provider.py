from __future__ import annotations

from app.config import settings


def is_openai_configured() -> bool:
    return bool(settings.openai_api_key)


def is_anthropic_configured() -> bool:
    return bool(settings.anthropic_api_key)
