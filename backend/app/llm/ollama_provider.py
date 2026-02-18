from __future__ import annotations

import httpx
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def check_ollama_available() -> bool:
    """Check if Ollama server is running and reachable."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


async def list_ollama_models() -> list[str]:
    """List available models on the Ollama server."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        logger.warning("Failed to list Ollama models: %s", e)
    return []
