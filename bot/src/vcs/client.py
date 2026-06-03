"""
VCS-клиент — заглушка подключения к видеоконференции.
Интерфейс зафиксирован; реальная реализация (Zoom SDK / WebRTC) подключается позже.

Конкретные реализации наследуются от BaseVCSClient и переопределяют:
  connect()     — войти в конференцию
  disconnect()  — выйти
  send_audio()  — отправить PCM-фрейм в виртуальный микрофон
  recv_audio()  — получить PCM-фрейм от участников
"""

from __future__ import annotations
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class VCSPlatformType(str, Enum):
    ZOOM = "zoom"
    YANDEX = "yandex"
    MEET = "meet"


@dataclass
class VCSConnectionInfo:
    platform: VCSPlatformType
    link: str
    display_name: str = "Помощник преподавателя"


class BaseVCSClient(ABC):
    def __init__(self, info: VCSConnectionInfo):
        self.info = info
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
    """
    Заглушка для разработки и тестирования.
    Логирует вызовы, ничего реального не делает.
    """

    async def connect(self) -> None:
        await asyncio.sleep(0.5)   # эмулируем задержку подключения
        self.connected = True
        logger.info("[VCS-stub] Подключились к %s %s", self.info.platform, self.info.link)

    async def disconnect(self) -> None:
        await asyncio.sleep(0.1)
        self.connected = False
        logger.info("[VCS-stub] Отключились от %s", self.info.link)

    async def send_audio(self, pcm_frame: bytes) -> None:
        # В реальной реализации: отправка в виртуальный аудиодрайвер
        logger.debug("[VCS-stub] send_audio %d bytes", len(pcm_frame))

    async def recv_audio(self) -> bytes:
        # В реальной реализации: чтение из аудиопотока конференции
        await asyncio.sleep(0.02)  # ~50 фреймов/сек
        return b""


def make_vcs_client(info: VCSConnectionInfo) -> BaseVCSClient:
    """Фабрика: возвращает нужную реализацию по платформе."""
    # Сейчас все платформы идут через заглушку.
    # Позже: if info.platform == VCSPlatformType.ZOOM: return ZoomClient(info)
    return StubVCSClient(info)
