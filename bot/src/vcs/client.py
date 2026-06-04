"""
VCS-клиент — базовый интерфейс и фабрика.

Архитектура:
  BaseVCSClient          — абстрактный контракт
  ├── ZoomClient         — Playwright + Zoom Web Client
  ├── YandexClient       — Playwright + Яндекс Телемост
  └── StubVCSClient      — заглушка (dev / CI / VCS_STUB_MODE=true)

Фабрика make_vcs_client() учитывает:
  - VCS_STUB_MODE=true → всегда StubVCSClient
  - playwright не установлен → StubVCSClient + предупреждение
  - иначе → нужная платформенная реализация
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class VCSPlatformType(str, Enum):
    ZOOM   = "zoom"
    YANDEX = "yandex"
    MEET   = "meet"


@dataclass
class VCSConnectionInfo:
    platform:     VCSPlatformType
    link:         str
    display_name: str = "Помощник преподавателя"


class BaseVCSClient(ABC):
    def __init__(self, info: VCSConnectionInfo):
        self.info      = info
        self.connected = False

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def send_audio(self, pcm_frame: bytes) -> None: ...

    @abstractmethod
    async def recv_audio(self) -> bytes: ...


class StubVCSClient(BaseVCSClient):
    """Заглушка — логирует вызовы, реального браузера не запускает."""

    async def connect(self) -> None:
        await asyncio.sleep(0.3)
        self.connected = True
        logger.info("[VCS-stub] connect  platform=%s  link=%s", self.info.platform, self.info.link)

    async def disconnect(self) -> None:
        await asyncio.sleep(0.1)
        self.connected = False
        logger.info("[VCS-stub] disconnect")

    async def send_audio(self, pcm_frame: bytes) -> None:
        logger.debug("[VCS-stub] send_audio %d bytes", len(pcm_frame))

    async def recv_audio(self) -> bytes:
        await asyncio.sleep(0.02)
        return b""


def make_vcs_client(info: VCSConnectionInfo) -> BaseVCSClient:
    """
    Фабрика VCS-клиентов.

    Порядок выбора реализации:
      1. VCS_STUB_MODE=true  → StubVCSClient (явное отключение браузера)
      2. playwright недоступен → StubVCSClient + WARNING в лог
      3. zoom   → ZoomClient
      4. yandex → YandexClient
      5. иное   → StubVCSClient + WARNING
    """
    from config.settings import config

    if config.vcs_stub_mode:
        logger.info("[VCS] stub-режим включён (VCS_STUB_MODE=true)")
        return StubVCSClient(info)

    if not _playwright_available():
        logger.warning(
            "[VCS] playwright не установлен — используем заглушку. "
            "Установите: pip install playwright && playwright install chromium"
        )
        return StubVCSClient(info)

    if info.platform == VCSPlatformType.ZOOM:
        from src.vcs.zoom import ZoomClient
        return ZoomClient(info)

    if info.platform == VCSPlatformType.YANDEX:
        from src.vcs.yandex import YandexClient
        return YandexClient(info)

    logger.warning("[VCS] Платформа %s не поддерживается, используем заглушку", info.platform)
    return StubVCSClient(info)


def _playwright_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False
