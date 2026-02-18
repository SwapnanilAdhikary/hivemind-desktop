from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.integrations.discord_client import discord_client
from app.agents.orchestrator import orchestrator, AgentState
from app.tracing.tracer import new_run_id
from app.websocket.manager import ws_manager
from app.db.database import async_session
from app.db.models import PlatformStatus

logger = logging.getLogger(__name__)


class DiscordAgent:
    """Listens for Discord DMs and mentions, routes through the orchestrator."""

    def __init__(self) -> None:
        self._running = False

    async def start(self) -> None:
        self._running = True
        discord_client.on_new_message(self._handle_message)
        discord_client.on_status_change(self._handle_status)

        logger.info("Discord agent starting...")
        await discord_client.start_bot()

    async def stop(self) -> None:
        self._running = False
        await discord_client.close()
        await self._update_status(False)

    async def _handle_message(self, data: dict) -> None:
        from app.db.models import Message

        sender = data.get("sender", "")
        sender_name = data.get("sender_name", sender)
        content = data.get("content", "")

        if not content:
            return

        logger.info("Discord message from %s: %s", sender_name, content[:50])

        channel_id = data.get("channel_id", "")

        async with async_session() as session:
            db_msg = Message(
                platform="discord",
                sender=sender,
                sender_name=sender_name,
                content=content,
                conversation_id=channel_id,
                metadata_json={
                    "channel_id": channel_id,
                    "message_id": data.get("message_id", ""),
                    "guild_name": data.get("guild_name", ""),
                    "is_dm": data.get("is_dm", False),
                },
            )
            session.add(db_msg)
            await session.commit()
            await session.refresh(db_msg)

        state: AgentState = {
            "run_id": new_run_id(),
            "platform": "discord",
            "sender": sender,
            "sender_name": sender_name,
            "content": content,
            "conversation_id": channel_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message_type": "dm" if data.get("is_dm") else "mention",
            "metadata": {
                "channel_id": channel_id,
                "message_id": data.get("message_id", ""),
                "guild_name": data.get("guild_name", ""),
                "is_dm": data.get("is_dm", False),
                "db_message_id": db_msg.id,
            },
        }

        try:
            await orchestrator.ainvoke(state)
        except Exception as e:
            logger.error("Orchestrator failed for Discord message: %s", e)

    async def send_reply(self, channel_id: str, text: str) -> None:
        await discord_client.send_reply(int(channel_id), text)

    async def _handle_status(self, connected: bool) -> None:
        await self._update_status(connected)

    async def _update_status(self, connected: bool, error: str = "") -> None:
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(PlatformStatus).where(PlatformStatus.platform == "discord")
            )
            row = result.scalar_one_or_none()
            if row:
                row.connected = connected
                row.error_message = error
                row.last_checked = datetime.utcnow()
            else:
                session.add(PlatformStatus(
                    platform="discord", connected=connected, error_message=error
                ))
            await session.commit()

        await ws_manager.broadcast("platform_status", {
            "platform": "discord",
            "connected": connected,
        })


discord_agent = DiscordAgent()
