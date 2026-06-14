"""
ZoomClient — подключение к Zoom Web Client через Playwright.

Поток:
  1. Парсим join-ссылку вида https://zoom.us/j/MEETING_ID?pwd=PASSWORD
  2. Открываем https://app.zoom.us/wc/join/MEETING_ID
  3. Вводим имя участника, разрешаем микрофон, нажимаем «Join»
  4. Ждём окончания join-процесса (появление аудио-кнопки / toolbar)
  5. Выключаем видео (бот без камеры)

Zoom Web Client (app.zoom.us/wc) — единственный способ войти в Zoom без
Desktop SDK. Он полностью работает в браузере, поддерживает headless Chromium
при правильных флагах.

Важно: Zoom периодически меняет CSS-селекторы. При поломке — обновить
константы SELECTORS ниже.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse, parse_qs

from src.vcs.base import PlaywrightVCSBase, UI_TIMEOUT
from src.vcs.client import VCSConnectionInfo

logger = logging.getLogger(__name__)


# ── Селекторы Zoom Web Client ──────────────────────────────────────────────
# Обновлять при изменении вёрстки Zoom
class ZoomSel:
    # Экран ввода имени
    NAME_INPUT       = 'input[placeholder*="name" i], input[placeholder*="имя" i], #inputname'
    JOIN_BTN         = 'button[class*="join" i]:visible, button:has-text("Join"):visible'

    # Диалог выбора аудио
    AUDIO_JOIN_BTN   = (
        'button:has-text("Join Audio"):visible, '
        'button:has-text("Join with Computer Audio"):visible, '
        'button[class*="audio-join" i]:visible'
    )
    COMPUTER_AUDIO   = (
        'button:has-text("Computer Audio"):visible, '
        'a:has-text("Computer Audio"):visible'
    )

    # Тулбар — признак успешного входа
    TOOLBAR          = '.footer-button-base__button, [class*="toolbar" i] button'

    # Кнопки управления
    MUTE_BTN         = '[aria-label*="mute" i]:visible, [aria-label*="микрофон" i]:visible'
    LEAVE_BTN        = (
        'button[aria-label*="Leave" i]:visible, '
        'button[aria-label*="End" i]:visible, '
        'button:has-text("Leave"):visible'
    )
    LEAVE_CONFIRM    = 'button:has-text("Leave Meeting"):visible'
    VIDEO_OFF_BTN    = '[aria-label*="stop video" i]:visible, [aria-label*="видео" i]:visible'
    DONT_USE_APP     = (
        'a:has-text("join from your browser"):visible, '
        'a:has-text("Launch Meeting"):visible + a, '
        'a[href*="?preferwebclient"]:visible'
    )


def _parse_zoom_link(link: str) -> tuple[str, str]:
    """Вернуть (meeting_id, password) из zoom-ссылки."""
    # Формат 1: https://zoom.us/j/MEETING_ID?pwd=PASSWORD
    # Формат 2: https://us06web.zoom.us/j/MEETING_ID?pwd=PASSWORD
    parsed = urlparse(link)
    path_parts = parsed.path.strip("/").split("/")

    meeting_id = ""
    if "j" in path_parts:
        idx = path_parts.index("j")
        if idx + 1 < len(path_parts):
            meeting_id = path_parts[idx + 1]

    qs = parse_qs(parsed.query)
    password = qs.get("pwd", [""])[0]

    if not meeting_id:
        # Попробовать найти числа в пути
        nums = re.findall(r"\d{9,}", link)
        meeting_id = nums[0] if nums else ""

    return meeting_id, password


class ZoomClient(PlaywrightVCSBase):

    def __init__(self, info: VCSConnectionInfo):
        super().__init__(info)
        self._meeting_id, self._password = _parse_zoom_link(info.link)
        if not self._meeting_id:
            raise ValueError(f"Не удалось извлечь meeting_id из ссылки: {info.link}")

    async def _join_conference(self) -> None:
        page = self._page
        pwd_param = f"?pwd={self._password}" if self._password else ""
        web_url = f"https://app.zoom.us/wc/join/{self._meeting_id}{pwd_param}"

        logger.info("[Zoom] Открываем %s", web_url)
        await page.goto(web_url, wait_until="domcontentloaded", timeout=30_000)

        # Ссылка «join from your browser» — убедимся что в веб-клиенте
        try:
            link = await page.wait_for_selector(ZoomSel.DONT_USE_APP, timeout=5_000)
            if link:
                await link.click()
                await page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass  # уже в веб-клиенте

        # Ввести имя участника
        try:
            name_input = await page.wait_for_selector(ZoomSel.NAME_INPUT, timeout=UI_TIMEOUT)
            await name_input.fill("")
            await name_input.type(self.info.display_name, delay=50)
        except Exception as e:
            logger.warning("[Zoom] Поле имени не найдено: %s", e)

        # Нажать «Join»
        try:
            join = await page.wait_for_selector(ZoomSel.JOIN_BTN, timeout=UI_TIMEOUT)
            await join.click()
        except Exception as e:
            logger.warning("[Zoom] Кнопка Join не найдена: %s", e)

        # Выбрать Computer Audio
        try:
            computer_audio = await page.wait_for_selector(ZoomSel.COMPUTER_AUDIO, timeout=10_000)
            await computer_audio.click()
        except Exception:
            pass

        try:
            audio_join = await page.wait_for_selector(ZoomSel.AUDIO_JOIN_BTN, timeout=10_000)
            await audio_join.click()
        except Exception:
            pass

        # Ждём тулбар — признак успешного входа
        try:
            await page.wait_for_selector(ZoomSel.TOOLBAR, timeout=UI_TIMEOUT)
            logger.info("[Zoom] Тулбар появился — вход в комнату успешен")
        except Exception:
            logger.warning("[Zoom] Тулбар не дождались, продолжаем")

        # Выключить видео (бот без камеры)
        try:
            video_btn = page.locator(ZoomSel.VIDEO_OFF_BTN)
            if await video_btn.count() > 0:
                await video_btn.first.click()
        except Exception:
            pass

        logger.info("[Zoom] Бот в комнате. Meeting ID: %s", self._meeting_id)

    async def _leave_conference(self) -> None:
        page = self._page
        try:
            leave = page.locator(ZoomSel.LEAVE_BTN)
            if await leave.count() > 0:
                await leave.first.click()
                # Подтверждение
                try:
                    confirm = await page.wait_for_selector(ZoomSel.LEAVE_CONFIRM, timeout=3_000)
                    await confirm.click()
                except Exception:
                    pass
        except Exception as e:
            logger.warning("[Zoom] Не удалось нажать Leave: %s", e)
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
