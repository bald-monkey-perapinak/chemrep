"""
EventBus — внутришний pub/sub для SSE-событий урока.

Архитектура:
  - Бот (LessonRunner) вызывает event_bus.publish(lesson_id, event)
  - SSE-роутер подписывается на lesson_id через event_bus.subscribe()
  - Каждый SSE-клиент получает asyncio.Queue, в которую падают события

Это in-process решение: работает в рамках одного процесса FastAPI.
При горизонтальном масштабировании (несколько воркеров uvicorn) —
заменить на Redis Pub/Sub, подключив asyncio-redis.

Типы событий (поле "kind"):
  session_started   — бот создал сессию, урок IN_PROGRESS
  bot_joined        — бот вошёл в конференцию
  step_started      — начат новый шаг сценария
  board_action      — действие на доске
  question_asked    — бот задал вопрос ученику
  student_speech    — ученик что-то сказал
  student_question  — ученик задал вопрос (free dialog)
  bot_reply         — бот ответил через LLM
  homework_sent     — ДЗ отправлено на email
  session_ended     — урок завершён нормально
  session_failed    — урок завершился с ошибкой
  heartbeat         — keepalive каждые 15 сек
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self):
        # lesson_id → список очередей активных SSE-клиентов
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, lesson_id: str | UUID) -> asyncio.Queue:
        """Зарегистрировать нового SSE-клиента. Вернуть его очередь."""
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers[str(lesson_id)].append(q)
        logger.debug("[EventBus] subscribe lesson=%s  total=%d",
                     lesson_id, len(self._subscribers[str(lesson_id)]))
        return q

    def unsubscribe(self, lesson_id: str | UUID, q: asyncio.Queue) -> None:
        """Отписать клиента при разрыве SSE-соединения."""
        key = str(lesson_id)
        try:
            self._subscribers[key].remove(q)
        except ValueError:
            pass
        if not self._subscribers[key]:
            del self._subscribers[key]
        logger.debug("[EventBus] unsubscribe lesson=%s", lesson_id)

    def publish(self, lesson_id: str | UUID, kind: str, data: dict[str, Any] | None = None) -> None:
        """
        Опубликовать событие для урока.
        Вызывается из бота (синхронно из asyncio-контекста).
        """
        key = str(lesson_id)
        if key not in self._subscribers:
            return   # нет подписчиков — пропускаем

        event = {
            "kind": kind,
            "ts":   datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        }
        dead: list[asyncio.Queue] = []
        for q in list(self._subscribers[key]):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("[EventBus] queue full for lesson=%s, dropping event", lesson_id)
            except Exception:
                dead.append(q)

        for q in dead:
            self.unsubscribe(lesson_id, q)

    def subscriber_count(self, lesson_id: str | UUID) -> int:
        return len(self._subscribers.get(str(lesson_id), []))


# Синглтон — используется и в боте, и в бэкенде
event_bus = EventBus()
