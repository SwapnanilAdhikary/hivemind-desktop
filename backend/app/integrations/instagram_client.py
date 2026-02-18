from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class InstagramClient:
    """Instagram DM client using instagrapi."""

    def __init__(self) -> None:
        self._client = None
        self._logged_in = False

    @property
    def client(self):
        if self._client is None:
            from instagrapi import Client
            self._client = Client()
        return self._client

    def is_configured(self) -> bool:
        return bool(settings.instagram_username and settings.instagram_password)

    def login(self) -> bool:
        if not self.is_configured():
            logger.warning("Instagram credentials not configured")
            return False
        try:
            self.client.login(settings.instagram_username, settings.instagram_password)
            self._logged_in = True
            logger.info("Instagram logged in as %s", settings.instagram_username)
            return True
        except Exception as e:
            logger.error("Instagram login failed: %s", e)
            return False

    def fetch_recent_dms(self, amount: int = 10) -> list[dict[str, Any]]:
        """Fetch recent direct message threads."""
        if not self._logged_in:
            if not self.login():
                return []

        try:
            threads = self.client.direct_threads(amount=amount)
            messages = []

            for thread in threads:
                if not thread.messages:
                    continue
                last_msg = thread.messages[0]

                if last_msg.user_id == self.client.user_id:
                    continue

                sender_info = None
                for user in thread.users:
                    if user.pk == last_msg.user_id:
                        sender_info = user
                        break

                text = ""
                if last_msg.text:
                    text = last_msg.text
                elif last_msg.item_type == "media_share":
                    text = "[Shared media]"
                elif last_msg.item_type == "reel_share":
                    text = "[Shared reel]"
                elif last_msg.item_type == "story_share":
                    text = "[Shared story]"
                else:
                    text = f"[{last_msg.item_type}]"

                messages.append({
                    "thread_id": str(thread.id),
                    "sender_id": str(last_msg.user_id),
                    "sender_name": sender_info.username if sender_info else str(last_msg.user_id),
                    "sender_full_name": sender_info.full_name if sender_info else "",
                    "content": text,
                    "timestamp": last_msg.timestamp.isoformat() if last_msg.timestamp else "",
                    "message_id": str(last_msg.id),
                })

            return messages
        except Exception as e:
            logger.error("Failed to fetch Instagram DMs: %s", e)
            return []

    def send_dm(self, thread_id: str, text: str) -> bool:
        """Send a direct message reply."""
        if not self._logged_in:
            if not self.login():
                return False
        try:
            self.client.direct_send(text, thread_ids=[int(thread_id)])
            logger.info("Sent Instagram DM to thread %s", thread_id)
            return True
        except Exception as e:
            logger.error("Failed to send Instagram DM: %s", e)
            return False

    def send_dm_to_user(self, user_id: str, text: str) -> bool:
        """Send a DM to a specific user by their user ID."""
        if not self._logged_in:
            if not self.login():
                return False
        try:
            self.client.direct_send(text, user_ids=[int(user_id)])
            return True
        except Exception as e:
            logger.error("Failed to send Instagram DM to user %s: %s", user_id, e)
            return False


instagram_client = InstagramClient()
