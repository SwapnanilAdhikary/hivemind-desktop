from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.integrations.gmail_client import gmail_client
from app.agents.orchestrator import orchestrator, AgentState
from app.tracing.tracer import new_run_id
from app.websocket.manager import ws_manager
from app.db.database import async_session
from app.db.models import PlatformStatus

logger = logging.getLogger(__name__)


class GmailAgent:
    """Polls Gmail for new emails and routes them through the orchestrator."""

    def __init__(self, poll_interval: int = 30) -> None:
        self.poll_interval = poll_interval
        self._running = False
        self._seen_ids: set[str] = set()

    async def start(self) -> None:
        if not gmail_client.is_configured():
            logger.warning("Gmail not configured -- skipping agent start")
            return

        self._running = True
        logger.info("Gmail agent started (polling every %ds)", self.poll_interval)
        await self._update_status(True)

        while self._running:
            try:
                await self._poll()
            except Exception as e:
                logger.error("Gmail poll error: %s", e)
                await self._update_status(False, str(e))
            await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        self._running = False
        await self._update_status(False)

    async def _poll(self) -> None:
        emails = await asyncio.to_thread(gmail_client.fetch_recent_emails, 5)

        for email in emails:
            if email["id"] in self._seen_ids:
                continue
            self._seen_ids.add(email["id"])

            logger.info("New email from %s: %s", email["sender"], email["subject"])

            state: AgentState = {
                "run_id": new_run_id(),
                "platform": "gmail",
                "sender": email["sender"],
                "sender_name": email["sender"].split("<")[0].strip(),
                "content": f"Subject: {email['subject']}\n\n{email['body'][:1000]}",
                "conversation_id": email["thread_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "message_type": "email",
                "metadata": {
                    "email_id": email["id"],
                    "thread_id": email["thread_id"],
                    "subject": email["subject"],
                },
            }

            try:
                await orchestrator.ainvoke(state)
            except Exception as e:
                logger.error("Orchestrator failed for email %s: %s", email["id"], e)

    async def send_reply(self, thread_id: str, to: str, subject: str, body: str) -> dict:
        return await asyncio.to_thread(gmail_client.send_reply, thread_id, to, subject, body)

    async def _update_status(self, connected: bool, error: str = "") -> None:
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(PlatformStatus).where(PlatformStatus.platform == "gmail")
            )
            row = result.scalar_one_or_none()
            if row:
                row.connected = connected
                row.error_message = error
                row.last_checked = datetime.utcnow()
            else:
                session.add(PlatformStatus(
                    platform="gmail", connected=connected, error_message=error
                ))
            await session.commit()

        await ws_manager.broadcast("platform_status", {
            "platform": "gmail",
            "connected": connected,
            "error": error,
        })


gmail_agent = GmailAgent()
