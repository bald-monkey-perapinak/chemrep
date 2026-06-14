"""
ReconnectManager — автоматическое переподключение к VCS при потере соединения.

Используется LessonRunner для resilience при нестабильной сети.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable, Optional

logger = logging.getLogger(__name__)

MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_DELAYS = [5, 15, 45]


def is_connection_error(exc: Exception) -> bool:
    """Определить, является ли ошибка потерей соединения VCS."""
    msg = str(exc).lower()
    keywords = (
        "connection", "disconnected", "not connected",
        "broken pipe", "reset by peer", "eof",
        "page closed", "target closed", "crash",
        "websocket", "timeout",
    )
    return any(kw in msg for kw in keywords)


class ReconnectManager:
    """
    Управляет попытками переподключения с exponential backoff.

    Использование:
        async def do_work():
            ...

        manager = ReconnectManager(on_reconnect=reconnect_fn)
        await manager.execute_with_reconnect(do_work)
    """

    def __init__(
        self,
        on_reconnect: Callable[[], Awaitable[bool]],
        on_event: Optional[Callable[[str, dict], None]] = None,
        max_attempts: int = MAX_RECONNECT_ATTEMPTS,
        delays: list[int] | None = None,
    ):
        self._on_reconnect = on_reconnect
        self._on_event = on_event or (lambda *a: None)
        self._max_attempts = max_attempts
        self._delays = delays or RECONNECT_DELAYS
        self._reconnect_count = 0

    @property
    def reconnect_count(self) -> int:
        return self._reconnect_count

    async def execute_with_reconnect(
        self,
        fn: Callable[[], Awaitable],
        operation_name: str = "operation",
    ) -> None:
        """Выполнить fn с автоматическим переподключением при connection error."""
        try:
            await fn()
        except Exception as e:
            if not is_connection_error(e):
                raise
            logger.warning("Потеря соединения при %s: %s", operation_name, e)
            if await self._reconnect():
                await fn()
            else:
                raise

    async def execute_with_reconnect_return(
        self,
        fn: Callable[[], Awaitable],
        operation_name: str = "operation",
    ):
        """Выполнить fn с reconnect, возвращая результат."""
        try:
            return await fn()
        except Exception as e:
            if not is_connection_error(e):
                raise
            logger.warning("Потеря соединения при %s: %s", operation_name, e)
            if await self._reconnect():
                return await fn()
            raise

    async def _reconnect(self) -> bool:
        """Попытка переподключения с exponential backoff."""
        for attempt in range(self._max_attempts):
            delay = self._delays[min(attempt, len(self._delays) - 1)]
            logger.warning(
                "Переподключение (попытка %d/%d, задержка %ds)...",
                attempt + 1, self._max_attempts, delay,
            )
            self._on_event("vcs_reconnect_attempt", {
                "attempt": attempt + 1,
                "max": self._max_attempts,
            })

            await asyncio.sleep(delay)

            try:
                if await self._on_reconnect():
                    self._reconnect_count += 1
                    logger.info("Переподключено (попытка %d)", attempt + 1)
                    self._on_event("vcs_reconnected", {"attempt": attempt + 1})
                    return True
            except Exception as e:
                logger.warning(
                    "Попытка %d/%d не удалась: %s",
                    attempt + 1, self._max_attempts, e,
                )

        logger.error("Все попытки переподключения исчерпаны")
        return False
