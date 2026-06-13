"""
SSE Router — стриминг событий урока в браузер через Server-Sent Events.

GET /api/sse/lessons/{lesson_id}
  — открывает постоянное соединение, шлёт события по мере их появления
  — браузер получает: data: {"kind": "step_started", "ts": "...", "data": {...}}\n\n
  — соединение живёт до закрытия вкладки или завершения урока

GET /api/sse/active
  — список lesson_id с активными подписчиками (для отладки)

Аутентификация:
  JWT-токен передаётся в query-параметре ?token=... (EventSource не поддерживает
  заголовки, поэтому используем query-параметр вместо Authorization header).

Keepalive:
  Каждые HEARTBEAT_INTERVAL секунд отправляем heartbeat-событие, чтобы
  прокси и браузеры не закрыли соединение по таймауту.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.db.base import get_db
from src.events.bus import event_bus
from src.models.lesson import Lesson
from src.models.teacher import Teacher
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sse", tags=["sse"])

HEARTBEAT_INTERVAL = 15   # секунд
ALGORITHM   = "HS256"

def _get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if not secret:
        import secrets
        secret = secrets.token_hex(32)
        os.environ["JWT_SECRET"] = secret
    return secret

SECRET_KEY = _get_jwt_secret()


# ── Auth через query-параметр (EventSource не поддерживает заголовки) ─────

def _teacher_from_token(token: str, db: Session) -> Teacher:
    try:
        payload    = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        teacher_id = payload.get("sub")
        if not teacher_id:
            raise ValueError("no sub")
    except (JWTError, ValueError):
        raise HTTPException(401, "Недействительный токен")

    teacher = db.query(Teacher).filter(
        Teacher.id == teacher_id,
        Teacher.is_active == True,  # noqa: E712
    ).first()
    if not teacher:
        raise HTTPException(401, "Преподаватель не найден")
    return teacher


# ── SSE-генератор ─────────────────────────────────────────────────────────

async def _event_generator(lesson_id: str, queue: asyncio.Queue):
    """
    Асинхронный генератор SSE-потока.
    Читает события из очереди и отдаёт в формате text/event-stream.
    """
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
                payload = json.dumps(event, ensure_ascii=False)
                yield f"data: {payload}\n\n"

                # Завершаем поток при финальных событиях
                if event.get("kind") in ("session_ended", "session_failed"):
                    logger.info("[SSE] lesson=%s завершён, закрываем поток", lesson_id)
                    return

            except asyncio.TimeoutError:
                # Keepalive — браузер не закроет соединение
                heartbeat = json.dumps({
                    "kind": "heartbeat",
                    "ts":   datetime.now(timezone.utc).isoformat(),
                    "data": {},
                })
                yield f"data: {heartbeat}\n\n"

    except asyncio.CancelledError:
        logger.info("[SSE] lesson=%s клиент отключился", lesson_id)
    finally:
        event_bus.unsubscribe(lesson_id, queue)


# ── Эндпоинты ─────────────────────────────────────────────────────────────

@router.get(
    "/lessons/{lesson_id}",
    summary="SSE-поток событий урока",
    description=(
        "Открывает Server-Sent Events соединение. Токен передаётся в query-параметре `token`. "
        "Браузер получает JSON-события по мере их появления: шаги сценария, реплики диалога, "
        "действия на Miro, статус бота. Поток закрывается при событии `session_ended` или `session_failed`."
    ),
    responses={
        200: {"content": {"text/event-stream": {}}},
    },
)
async def lesson_events(
    lesson_id: UUID,
    token: str = Query(..., description="JWT-токен преподавателя"),
    db:    Session = Depends(get_db),
):
    # Аутентификация
    teacher = _teacher_from_token(token, db)

    # Проверить что урок принадлежит преподавателю
    lesson = db.query(Lesson).filter(
        Lesson.id == lesson_id,
        Lesson.teacher_id == teacher.id,
    ).first()
    if not lesson:
        raise HTTPException(404, "Занятие не найдено")

    # Подписаться на события
    queue = event_bus.subscribe(lesson_id)
    logger.info(
        "[SSE] lesson=%s teacher=%s подключился (подписчиков: %d)",
        lesson_id, teacher.id, event_bus.subscriber_count(lesson_id),
    )

    # Отправить текущее состояние сразу при подключении
    initial = {
        "kind": "connected",
        "ts":   datetime.now(timezone.utc).isoformat(),
        "data": {
            "lesson_id":   str(lesson_id),
            "lesson_status": lesson.status.value,
            "session_status": lesson.session.status.value if lesson.session else None,
            "current_step":  lesson.session.current_step if lesson.session else 0,
            "total_steps":   lesson.session.total_steps if lesson.session else None,
        },
    }
    await queue.put(initial)

    return StreamingResponse(
        _event_generator(str(lesson_id), queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control":       "no-cache",
            "X-Accel-Buffering":   "no",   # отключить буферизацию Nginx
            "Connection":          "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get(
    "/active",
    summary="Список уроков с активными SSE-подписчиками (отладка)",
    include_in_schema=False,
)
def active_subscriptions():
    return {
        lesson_id: event_bus.subscriber_count(lesson_id)
        for lesson_id in event_bus._subscribers
    }
