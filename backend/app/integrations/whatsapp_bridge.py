from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

import websockets

from app.config import settings

logger = logging.getLogger(__name__)


class WhatsAppBridge:
    """Python-side connector to the Node.js Baileys WhatsApp bridge."""

    def __init__(self) -> None:
        self._ws: Any = None
        self._connected = False
        self._on_message: Callable[[dict], Coroutine] | None = None
        self._on_status_change: Callable[[bool], Coroutine] | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    def on_message(self, handler: Callable[[dict], Coroutine]) -> None:
        self._on_message = handler

    def on_status_change(self, handler: Callable[[bool], Coroutine]) -> None:
        self._on_status_change = handler

    async def connect(self) -> None:
        url = settings.whatsapp_bridge_url
        logger.info("Connecting to WhatsApp bridge at %s", url)

        while True:
            try:
                async with websockets.connect(url) as ws:
                    self._ws = ws
                    self._connected = True
                    logger.info("Connected to WhatsApp bridge")
                    if self._on_status_change:
                        await self._on_status_change(True)

                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                            await self._handle_message(msg)
                        except json.JSONDecodeError:
                            logger.warning("Invalid JSON from bridge: %s", raw[:100])

            except Exception as e:
                self._connected = False
                if self._on_status_change:
                    await self._on_status_change(False)
                logger.warning("WhatsApp bridge connection lost: %s. Retrying in 5s...", e)
                await asyncio.sleep(5)

    async def _handle_message(self, msg: dict) -> None:
        msg_type = msg.get("type")

        if msg_type == "new_message" and self._on_message:
            await self._on_message(msg.get("data", {}))
        elif msg_type == "connected":
            self._connected = True
            if self._on_status_change:
                await self._on_status_change(True)
        elif msg_type == "disconnected":
            self._connected = False
            if self._on_status_change:
                await self._on_status_change(False)
        elif msg_type == "qr":
            logger.info("WhatsApp QR code received -- display in frontend")

    async def send_message(self, jid: str, text: str) -> None:
        if not self._ws:
            raise ConnectionError("WhatsApp bridge WebSocket not connected")
        logger.info("Sending WhatsApp message to %s: %s", jid, text[:50])
        await self._ws.send(json.dumps({
            "type": "send_message",
            "jid": jid,
            "text": text,
        }))

    async def get_status(self) -> bool:
        if not self._ws:
            return False
        try:
            await self._ws.send(json.dumps({"type": "get_status"}))
            return self._connected
        except Exception:
            return False


whatsapp_bridge = WhatsAppBridge()
