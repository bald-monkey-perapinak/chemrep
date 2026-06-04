"""
Юнит-тесты VCS-слоя.

Запуск:
    cd bot
    pytest tests/test_vcs.py -v

Тесты не требуют браузера или БД: playwright-зависимость отсутствует в тестовой среде,
поэтому фабрика автоматически откатывается на StubVCSClient.
"""

import asyncio
import os
import sys

import pytest

# Добавляем пути так же, как в основном коде
_bot_root = os.path.dirname(os.path.dirname(__file__))
_backend_root = os.path.join(_bot_root, "..", "backend")
for p in (_bot_root, _backend_root):
    p = os.path.abspath(p)
    if p not in sys.path:
        sys.path.insert(0, p)

# Принудительно включаем stub-режим, чтобы тесты не запускали браузер
os.environ["VCS_STUB_MODE"] = "true"

from src.vcs.client import (
    VCSConnectionInfo,
    VCSPlatformType,
    StubVCSClient,
    make_vcs_client,
)
from src.vcs.zoom import _parse_zoom_link
from src.vcs.yandex import _parse_yandex_link


# ═══════════════════════════════════════════════════════════════════════════
#  Парсинг ссылок
# ═══════════════════════════════════════════════════════════════════════════

class TestZoomLinkParsing:
    def test_standard_link(self):
        mid, pwd = _parse_zoom_link("https://zoom.us/j/123456789?pwd=ABCDEF")
        assert mid == "123456789"
        assert pwd == "ABCDEF"

    def test_regional_link(self):
        mid, pwd = _parse_zoom_link("https://us06web.zoom.us/j/987654321?pwd=XYZ")
        assert mid == "987654321"
        assert pwd == "XYZ"

    def test_link_no_password(self):
        mid, pwd = _parse_zoom_link("https://zoom.us/j/111222333")
        assert mid == "111222333"
        assert pwd == ""

    def test_invalid_link_returns_empty(self):
        mid, pwd = _parse_zoom_link("https://example.com/meeting")
        # meeting_id либо пустой, либо извлечён из цифр — главное нет исключения
        assert isinstance(mid, str)
        assert isinstance(pwd, str)


class TestYandexLinkParsing:
    def test_standard_link(self):
        code = _parse_yandex_link("https://telemost.yandex.ru/j/ROOM123ABC")
        assert code == "ROOM123ABC"

    def test_link_with_trailing_slash(self):
        code = _parse_yandex_link("https://telemost.yandex.ru/j/MYROOM/")
        assert code == "MYROOM"

    def test_invalid_link(self):
        code = _parse_yandex_link("https://telemost.yandex.ru/")
        assert isinstance(code, str)


# ═══════════════════════════════════════════════════════════════════════════
#  Фабрика make_vcs_client
# ═══════════════════════════════════════════════════════════════════════════

class TestFactory:
    def _info(self, platform: VCSPlatformType, link: str = "https://example.com") -> VCSConnectionInfo:
        return VCSConnectionInfo(platform=platform, link=link)

    def test_zoom_returns_stub_in_stub_mode(self):
        client = make_vcs_client(self._info(VCSPlatformType.ZOOM, "https://zoom.us/j/123"))
        assert isinstance(client, StubVCSClient)

    def test_yandex_returns_stub_in_stub_mode(self):
        client = make_vcs_client(self._info(VCSPlatformType.YANDEX, "https://telemost.yandex.ru/j/ABC"))
        assert isinstance(client, StubVCSClient)

    def test_unknown_platform_returns_stub(self):
        client = make_vcs_client(self._info(VCSPlatformType.MEET))
        assert isinstance(client, StubVCSClient)

    def test_custom_display_name_preserved(self):
        info = VCSConnectionInfo(
            platform=VCSPlatformType.ZOOM,
            link="https://zoom.us/j/999",
            display_name="Иванова А.П.",
        )
        client = make_vcs_client(info)
        assert client.info.display_name == "Иванова А.П."


# ═══════════════════════════════════════════════════════════════════════════
#  StubVCSClient — поведение
# ═══════════════════════════════════════════════════════════════════════════

class TestStubVCSClient:
    def _make(self) -> StubVCSClient:
        return StubVCSClient(VCSConnectionInfo(
            platform=VCSPlatformType.ZOOM,
            link="https://zoom.us/j/000",
        ))

    def test_initial_not_connected(self):
        client = self._make()
        assert client.connected is False

    def test_connect_sets_connected(self):
        client = self._make()
        asyncio.get_event_loop().run_until_complete(client.connect())
        assert client.connected is True

    def test_disconnect_clears_connected(self):
        client = self._make()
        asyncio.get_event_loop().run_until_complete(client.connect())
        asyncio.get_event_loop().run_until_complete(client.disconnect())
        assert client.connected is False

    def test_send_audio_accepts_bytes(self):
        client = self._make()
        pcm = bytes(320)  # 20ms фрейм тишины
        asyncio.get_event_loop().run_until_complete(client.send_audio(pcm))

    def test_recv_audio_returns_bytes(self):
        client = self._make()
        result = asyncio.get_event_loop().run_until_complete(client.recv_audio())
        assert isinstance(result, bytes)

    def test_full_lifecycle(self):
        """connect → send → recv → disconnect без исключений."""
        client = self._make()
        loop = asyncio.get_event_loop()

        loop.run_until_complete(client.connect())
        assert client.connected

        loop.run_until_complete(client.send_audio(b"\x00" * 640))
        audio = loop.run_until_complete(client.recv_audio())
        assert isinstance(audio, bytes)

        loop.run_until_complete(client.disconnect())
        assert not client.connected

    def test_connect_disconnect_idempotent(self):
        """Двойное подключение/отключение не должно падать."""
        client = self._make()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(client.connect())
        loop.run_until_complete(client.connect())   # повторно
        loop.run_until_complete(client.disconnect())
        loop.run_until_complete(client.disconnect())  # повторно

    def test_send_empty_frame(self):
        client = self._make()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(client.send_audio(b""))  # не должно падать
