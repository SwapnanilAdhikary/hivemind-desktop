from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.integrations.whatsapp_bridge import whatsapp_bridge
from app.agents.orchestrator import orchestrator, AgentState
from app.tracing.tracer import new_run_id
from app.websocket.manager import ws_manager
from app.db.database import async_session
from app.db.models import PlatformStatus

logger = logging.getLogger(__name__)


class WhatsAppAgent:
    """Listens for WhatsApp messages via the Baileys bridge and routes through orchestrator."""

    def __init__(self) -> None:
        self._running = False

    async def start(self) -> None:
        self._running = True
        whatsapp_bridge.on_message(self._handle_message)
        whatsapp_bridge.on_status_change(self._handle_status)

        logger.info("WhatsApp agent started")
        await whatsapp_bridge.connect()

    async def stop(self) -> None:
        self._running = False
        await self._update_status(False)

    async def _handle_message(self, data: dict) -> None:
        from app.db.models import Message

        sender = data.get("sender", "")
        sender_name = data.get("sender_name", sender.split("@")[0])
        content = data.get("content", "")
        is_group = data.get("is_group", False)

        if not content:
            return

        logger.info("WhatsApp message from %s: %s", sender_name, content[:50])

        # Save to DB first so we have a message ID for replies
        async with async_session() as session:
            db_msg = Message(
                platform="whatsapp",
                sender=sender,
                sender_name=sender_name,
                content=content,
                conversation_id=sender,
                metadata_json={
                    "is_group": is_group,
                    "message_id": data.get("message_id", ""),
                },
            )
            session.add(db_msg)
            await session.commit()
            await session.refresh(db_msg)

        state: AgentState = {
            "run_id": new_run_id(),
            "platform": "whatsapp",
            "sender": sender,
            "sender_name": sender_name,
            "content": content,
            "conversation_id": sender,
            "timestamp": datetime.utcnow().isoformat(),
            "message_type": "chat",
            "metadata": {
                "is_group": is_group,
                "message_id": data.get("message_id", ""),
                "db_message_id": db_msg.id,
            },
        }

        try:
            await orchestrator.ainvoke(state)
        except Exception as e:
            logger.error("Orchestrator failed for WhatsApp message: %s", e)

    async def send_reply(self, jid: str, text: str) -> None:
        await whatsapp_bridge.send_message(jid, text)

    async def _handle_status(self, connected: bool) -> None:
        await self._update_status(connected)

    async def _update_status(self, connected: bool, error: str = "") -> None:
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(PlatformStatus).where(PlatformStatus.platform == "whatsapp")
            )
            row = result.scalar_one_or_none()
            if row:
                row.connected = connected
                row.error_message = error
                row.last_checked = datetime.utcnow()
            else:
                session.add(PlatformStatus(
                    platform="whatsapp", connected=connected, error_message=error
                ))
            await session.commit()

        await ws_manager.broadcast("platform_status", {
            "platform": "whatsapp",
            "connected": connected,
        })


whatsapp_agent = WhatsAppAgent()
