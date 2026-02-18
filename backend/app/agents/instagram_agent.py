from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.integrations.instagram_client import instagram_client
from app.agents.orchestrator import orchestrator, AgentState
from app.tracing.tracer import new_run_id
from app.websocket.manager import ws_manager
from app.db.database import async_session
from app.db.models import PlatformStatus

logger = logging.getLogger(__name__)


class InstagramAgent:
    """Polls Instagram DMs and routes through the orchestrator."""

    def __init__(self, poll_interval: int = 60) -> None:
        self.poll_interval = poll_interval
        self._running = False
        self._seen_ids: set[str] = set()

    async def start(self) -> None:
        if not instagram_client.is_configured():
            logger.warning("Instagram not configured -- skipping agent start")
            return

        logged_in = await asyncio.to_thread(instagram_client.login)
        if not logged_in:
            logger.error("Instagram login failed -- agent not started")
            await self._update_status(False, "Login failed")
            return

        self._running = True
        logger.info("Instagram agent started (polling every %ds)", self.poll_interval)
        await self._update_status(True)

        while self._running:
            try:
                await self._poll()
            except Exception as e:
                logger.error("Instagram poll error: %s", e)
                await self._update_status(False, str(e))
            await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        self._running = False
        await self._update_status(False)

    async def _poll(self) -> None:
        dms = await asyncio.to_thread(instagram_client.fetch_recent_dms, 5)

        for dm in dms:
            if dm["message_id"] in self._seen_ids:
                continue
            self._seen_ids.add(dm["message_id"])

            logger.info("New Instagram DM from %s: %s", dm["sender_name"], dm["content"][:50])

            state: AgentState = {
                "run_id": new_run_id(),
                "platform": "instagram",
                "sender": dm["sender_id"],
                "sender_name": dm.get("sender_full_name") or dm["sender_name"],
                "content": dm["content"],
                "conversation_id": dm["thread_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "message_type": "dm",
                "metadata": {
                    "thread_id": dm["thread_id"],
                    "message_id": dm["message_id"],
                    "sender_username": dm["sender_name"],
                },
            }

            try:
                await orchestrator.ainvoke(state)
            except Exception as e:
                logger.error("Orchestrator failed for Instagram DM: %s", e)

    async def send_reply(self, thread_id: str, text: str) -> bool:
        return await asyncio.to_thread(instagram_client.send_dm, thread_id, text)

    async def _update_status(self, connected: bool, error: str = "") -> None:
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(PlatformStatus).where(PlatformStatus.platform == "instagram")
            )
            row = result.scalar_one_or_none()
            if row:
                row.connected = connected
                row.error_message = error
                row.last_checked = datetime.utcnow()
            else:
                session.add(PlatformStatus(
                    platform="instagram", connected=connected, error_message=error
                ))
            await session.commit()

        await ws_manager.broadcast("platform_status", {
            "platform": "instagram",
            "connected": connected,
        })


instagram_agent = InstagramAgent()
