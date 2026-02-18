from __future__ import annotations

import asyncio
import logging
from typing import Callable, Coroutine

import discord

from app.config import settings

logger = logging.getLogger(__name__)


class DiscordClient(discord.Client):
    """Discord bot client that forwards messages to a callback handler."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        intents.guild_messages = True
        super().__init__(intents=intents)

        self._on_new_message: Callable[[dict], Coroutine] | None = None
        self._on_status_change: Callable[[bool], Coroutine] | None = None

    def on_new_message(self, handler: Callable[[dict], Coroutine]) -> None:
        self._on_new_message = handler

    def on_status_change(self, handler: Callable[[bool], Coroutine]) -> None:
        self._on_status_change = handler

    async def on_ready(self) -> None:
        logger.info("Discord bot connected as %s", self.user)
        if self._on_status_change:
            await self._on_status_change(True)

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return

        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mention = self.user in message.mentions if self.user else False

        if not is_dm and not is_mention:
            return

        data = {
            "sender": str(message.author),
            "sender_name": message.author.display_name,
            "content": message.content,
            "channel_id": str(message.channel.id),
            "message_id": str(message.id),
            "is_dm": is_dm,
            "guild_name": message.guild.name if message.guild else "DM",
        }

        if self._on_new_message:
            await self._on_new_message(data)

    async def send_reply(self, channel_id: int, content: str) -> None:
        channel = self.get_channel(channel_id)
        if channel is None:
            channel = await self.fetch_channel(channel_id)
        if channel and hasattr(channel, "send"):
            await channel.send(content)

    async def start_bot(self) -> None:
        token = settings.discord_bot_token
        if not token:
            logger.warning("Discord bot token not configured -- skipping")
            return
        try:
            await self.start(token)
        except Exception as e:
            logger.error("Discord bot failed: %s", e)
            if self._on_status_change:
                await self._on_status_change(False)


discord_client = DiscordClient()
