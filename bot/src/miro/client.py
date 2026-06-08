"""
Miro Client — управление интерактивной доской во время урока.

Действия из lesson_script["miro_action"]:
  show_frame:<frame_id>       — сфокусировать доску на фрейме
  create_sticky:<text>        — создать стикер с текстом
  create_text:<text>          — создать текстовый блок
  draw_shape:<shape>:<label>  — нарисовать фигуру (rectangle, circle, triangle)
  highlight:<item_id>         — выделить элемент
  clear_highlights            — снять все выделения
  zoom_in / zoom_out          — изменить масштаб

Документация API: https://developers.miro.com/reference/api-reference

Режимы:
  Реальный: MIRO_ACCESS_TOKEN задан
  Stub:     MIRO_STUB_MODE=true или нет токена — логирует вызовы
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MIRO_API = "https://api.miro.com/v2"


# ──────────────────────────────────────────────────────────────────────────
# Базовый класс
# ──────────────────────────────────────────────────────────────────────────

class BaseMiroClient(ABC):
    @abstractmethod
    async def execute(self, action: str) -> None:
        """Выполнить действие из сценария урока."""
        ...

    async def close(self) -> None:
        pass


# ──────────────────────────────────────────────────────────────────────────
# Заглушка
# ──────────────────────────────────────────────────────────────────────────

class StubMiroClient(BaseMiroClient):
    async def execute(self, action: str) -> None:
        logger.info("[Miro-stub] execute: %s", action)


# ──────────────────────────────────────────────────────────────────────────
# Реальный клиент
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class StickyNote:
    text:    str
    color:   str = "yellow"
    x:       float = 0.0
    y:       float = 0.0


class MiroClient(BaseMiroClient):
    """
    Управляет доской через Miro REST API v2.
    board_id берётся из KnowledgeTopic.miro_board_id.
    """

    def __init__(self, access_token: str, board_id: str):
        self._board_id = board_id
        self._client   = httpx.AsyncClient(
            base_url=MIRO_API,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type":  "application/json",
            },
            timeout=10.0,
        )

    async def execute(self, action: str) -> None:
        """Разобрать строку действия и вызвать нужный метод."""
        logger.info("[Miro] action=%s board=%s", action, self._board_id)
        try:
            await self._dispatch(action)
        except httpx.HTTPStatusError as e:
            logger.error("[Miro] HTTP %s: %s", e.response.status_code, e.response.text[:200])
        except Exception as e:
            logger.error("[Miro] Ошибка: %s", e)

    async def _dispatch(self, action: str) -> None:
        parts = action.split(":", 1)
        cmd   = parts[0].strip()
        arg   = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "show_frame":
            await self._show_frame(arg)
        elif cmd == "create_sticky":
            await self._create_sticky(arg)
        elif cmd == "create_text":
            await self._create_text(arg)
        elif cmd == "draw_shape":
            # draw_shape:rectangle:Алканы
            sub = arg.split(":", 1)
            shape = sub[0]
            label = sub[1] if len(sub) > 1 else ""
            await self._draw_shape(shape, label)
        elif cmd == "highlight":
            await self._highlight_item(arg)
        elif cmd == "clear_highlights":
            await self._clear_highlights()
        elif cmd == "zoom_in":
            await self._zoom(1.5)
        elif cmd == "zoom_out":
            await self._zoom(0.7)
        else:
            logger.warning("[Miro] Неизвестное действие: %s", cmd)

    # ── Конкретные действия ────────────────────────────────────────────────

    async def _show_frame(self, frame_id: str) -> None:
        """Переключить viewport на фрейм."""
        if not frame_id:
            return
        await self._client.post(
            f"/boards/{self._board_id}/frames/{frame_id}/zoom",
        )

    async def _create_sticky(self, text: str) -> None:
        """Создать стикер с текстом."""
        await self._client.post(
            f"/boards/{self._board_id}/sticky_notes",
            json={
                "data":  {"content": text, "shape": "square"},
                "style": {"fillColor": "yellow"},
                "geometry": {"width": 200},
            },
        )

    async def _create_text(self, text: str) -> None:
        """Создать текстовый блок."""
        await self._client.post(
            f"/boards/{self._board_id}/texts",
            json={
                "data":    {"content": text},
                "style":   {"fontSize": 24},
                "geometry": {"width": 400},
            },
        )

    async def _draw_shape(self, shape: str, label: str) -> None:
        """Нарисовать фигуру с подписью."""
        shape_map = {
            "rectangle": "rectangle",
            "circle":    "circle",
            "triangle":  "triangle",
            "rhombus":   "rhombus",
        }
        miro_shape = shape_map.get(shape, "rectangle")
        await self._client.post(
            f"/boards/{self._board_id}/shapes",
            json={
                "data":     {"content": label, "shape": miro_shape},
                "style":    {"fillColor": "#E6F1FB", "borderColor": "#185FA5"},
                "geometry": {"width": 200, "height": 120},
            },
        )

    async def _highlight_item(self, item_id: str) -> None:
        """Выделить существующий элемент (изменить цвет рамки)."""
        if not item_id:
            return
        # Пробуем обновить shape или sticky note
        for kind in ("shapes", "sticky_notes"):
            try:
                await self._client.patch(
                    f"/boards/{self._board_id}/{kind}/{item_id}",
                    json={"style": {"borderColor": "#FF5733", "borderWidth": 4}},
                )
                return
            except Exception:
                pass

    async def _clear_highlights(self) -> None:
        """Сбросить цвет рамок у всех shapes."""
        resp = await self._client.get(f"/boards/{self._board_id}/items?type=shape")
        if resp.status_code != 200:
            return
        items = resp.json().get("data", [])
        for item in items[:20]:   # не более 20, чтобы не затянуть урок
            try:
                await self._client.patch(
                    f"/boards/{self._board_id}/shapes/{item['id']}",
                    json={"style": {"borderColor": "#185FA5", "borderWidth": 2}},
                )
            except Exception:
                pass

    async def _zoom(self, factor: float) -> None:
        """Изменить масштаб viewport (API v2 не поддерживает напрямую — логируем)."""
        logger.info("[Miro] zoom factor=%.1f (управление viewport через клиент)", factor)

    async def close(self) -> None:
        await self._client.aclose()


# ──────────────────────────────────────────────────────────────────────────
# Фабрика
# ──────────────────────────────────────────────────────────────────────────

def make_miro_client(board_id: Optional[str] = None) -> BaseMiroClient:
    """
    Создать клиент для конкретной доски.
    Если токен не задан или MIRO_STUB_MODE=true — возвращает заглушку.
    """
    if os.getenv("MIRO_STUB_MODE", "false").lower() == "true":
        logger.info("[Miro] stub-режим (MIRO_STUB_MODE=true)")
        return StubMiroClient()

    token = os.getenv("MIRO_ACCESS_TOKEN", "")
    if not token:
        logger.warning("[Miro] MIRO_ACCESS_TOKEN не задан — используем заглушку")
        return StubMiroClient()

    if not board_id:
        logger.warning("[Miro] board_id не задан для темы — используем заглушку")
        return StubMiroClient()

    return MiroClient(access_token=token, board_id=board_id)
