"""
YandexClient — подключение к Яндекс Телемост через Playwright.

Яндекс Телемост (telemost.yandex.ru) — WebRTC-конференция, работает
в браузере без приложения. Отличия от Zoom:
  - Вход без авторизации: кнопка «Войти как гость»
  - Имя вводится в том же диалоге входа
  - Разрешение микрофона — системный диалог браузера (закрыт флагом Chromium)
  - Кнопки управления на русском языке

Ссылка вида: https://telemost.yandex.ru/j/ROOM_CODE
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from src.vcs.base import PlaywrightVCSBase, UI_TIMEOUT
from src.vcs.client import VCSConnectionInfo

logger = logging.getLogger(__name__)


class YaSel:
    # Экран входа
    GUEST_BTN      = (
        'button:has-text("Войти как гость"):visible, '
        'button:has-text("Продолжить без входа"):visible, '
        '[data-testid="join-as-guest"]:visible'
    )
    NAME_INPUT     = (
        'input[placeholder*="имя" i]:visible, '
        'input[placeholder*="name" i]:visible, '
        '[data-testid="name-input"]:visible'
    )
    JOIN_BTN       = (
        'button:has-text("Войти"):visible, '
        'button:has-text("Присоединиться"):visible, '
        '[data-testid="join-button"]:visible'
    )

    # Разрешение микрофона (появляется в некоторых конфигурациях)
    ALLOW_MIC      = (
        'button:has-text("Разрешить"):visible, '
        'button:has-text("Allow"):visible'
    )

    # Признак успешного входа
    ROOM_READY     = (
        '[data-testid="conference-room"]:visible, '
        '.conference-room:visible, '
        'button[aria-label*="микрофон" i]:visible, '
        'button[aria-label*="microphone" i]:visible'
    )

    # Управление
    MIC_BTN        = (
        'button[aria-label*="микрофон" i]:visible, '
        '[data-testid="mic-button"]:visible'
    )
    LEAVE_BTN      = (
        'button:has-text("Выйти"):visible, '
        'button:has-text("Покинуть"):visible, '
        '[data-testid="leave-button"]:visible, '
        'button[aria-label*="выйти" i]:visible'
    )
    LEAVE_CONFIRM  = (
        'button:has-text("Выйти из встречи"):visible, '
        'button:has-text("Покинуть встречу"):visible'
    )
    VIDEO_BTN      = (
        'button[aria-label*="камер" i]:visible, '
        '[data-testid="camera-button"]:visible'
    )


def _parse_yandex_link(link: str) -> str:
    """Вернуть room_code из ссылки Телемоста."""
    parsed = urlparse(link)
    parts = parsed.path.strip("/").split("/")
    # telemost.yandex.ru/j/ROOM_CODE
    if "j" in parts:
        idx = parts.index("j")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    # На случай нестандартных ссылок
    return parts[-1] if parts else ""


class YandexClient(PlaywrightVCSBase):

    def __init__(self, info: VCSConnectionInfo):
        super().__init__(info)
        self._room_code = _parse_yandex_link(info.link)
        if not self._room_code:
            raise ValueError(f"Не удалось извлечь room_code из ссылки: {info.link}")

    async def _join_conference(self) -> None:
        page = self._page
        url = f"https://telemost.yandex.ru/j/{self._room_code}"

        logger.info("[Yandex] Открываем %s", url)
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        # Кнопка «Войти как гость»
        try:
            guest_btn = await page.wait_for_selector(YaSel.GUEST_BTN, timeout=UI_TIMEOUT)
            await guest_btn.click()
        except Exception as e:
            logger.warning("[Yandex] Кнопка гостевого входа не найдена: %s", e)

        # Ввести имя
        try:
            name_input = await page.wait_for_selector(YaSel.NAME_INPUT, timeout=10_000)
            await name_input.fill("")
            await name_input.type(self.info.display_name, delay=50)
        except Exception as e:
            logger.warning("[Yandex] Поле имени не найдено: %s", e)

        # Разрешить микрофон если диалог появился
        try:
            allow = page.locator(YaSel.ALLOW_MIC)
            if await allow.count() > 0:
                await allow.first.click()
        except Exception:
            pass

        # Нажать «Войти» / «Присоединиться»
        try:
            join_btn = await page.wait_for_selector(YaSel.JOIN_BTN, timeout=UI_TIMEOUT)
            await join_btn.click()
        except Exception as e:
            logger.warning("[Yandex] Кнопка входа не найдена: %s", e)

        # Ждём появления комнаты
        try:
            await page.wait_for_selector(YaSel.ROOM_READY, timeout=UI_TIMEOUT)
            logger.info("[Yandex] Комната готова")
        except Exception:
            logger.warning("[Yandex] Комната не дождалась — продолжаем")

        # Выключить камеру
        try:
            video_btn = page.locator(YaSel.VIDEO_BTN)
            if await video_btn.count() > 0:
                await video_btn.first.click()
        except Exception:
            pass

        logger.info("[Yandex] Бот в комнате. Room: %s", self._room_code)

    async def _leave_conference(self) -> None:
        page = self._page
        try:
            leave = page.locator(YaSel.LEAVE_BTN)
            if await leave.count() > 0:
                await leave.first.click()
                try:
                    confirm = await page.wait_for_selector(YaSel.LEAVE_CONFIRM, timeout=3_000)
                    await confirm.click()
                except Exception:
                    pass
        except Exception as e:
            logger.warning("[Yandex] Не удалось нажать Выйти: %s", e)
        finally:
            await page.close()

    async def student_connected(self) -> bool:
        if not self._page:
            return False
        try:
            participants = self._page.locator(
                '[class*="participant" i]:visible, '
                '[data-testid*="participant"]:visible'
            )
            return await participants.count() > 1
        except Exception:
            return self.connected
