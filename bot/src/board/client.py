"""
BoardClient — WebSocket client for the whiteboard server.

Replaces MiroClient. Sends JSON commands to the whiteboard
which renders chemical formulas, equations, and SVG mechanisms.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BaseBoardClient(ABC):
    @abstractmethod
    async def execute(self, command: dict[str, Any]) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...


class StubBoardClient(BaseBoardClient):
    async def execute(self, command: dict[str, Any]) -> None:
        logger.info("[board:stub] %s", json.dumps(command, ensure_ascii=False))

    async def close(self) -> None:
        pass


class BoardClient(BaseBoardClient):
    def __init__(self, ws_url: str, session_id: str):
        self._ws_url = ws_url
        self._session_id = session_id
        self._ws = None

    async def _ensure_connected(self):
        if self._ws is not None:
            return
        import websockets
        url = f"{self._ws_url}/rooms/{self._session_id}"
        self._ws = await websockets.connect(url, ping_interval=20, ping_timeout=10)
        logger.info("[board] Connected to %s", url)

    async def execute(self, command: dict[str, Any]) -> None:
        try:
            await self._ensure_connected()
            await self._ws.send(json.dumps(command, ensure_ascii=False))
        except Exception as e:
            logger.error("[board] Send error: %s", e)
            self._ws = None

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None


def make_board_client(session_id: Optional[str] = None) -> BaseBoardClient:
    stub = os.getenv("BOARD_STUB_MODE", "false").lower() == "true"
    if stub or not session_id:
        return StubBoardClient()
    ws_url = os.getenv("BOARD_WS_URL", "ws://whiteboard:3001")
    return BoardClient(ws_url=ws_url, session_id=session_id)
