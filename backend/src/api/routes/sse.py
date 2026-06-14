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
from src.config.jwt import get_jwt_secret, ALGORITHM
from src.api.routes.auth import get_current_teacher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sse", tags=["sse"])

HEARTBEAT_INTERVAL = 15   # секунд
SECRET_KEY = get_jwt_secret()


# ── SSE Token endpoint (short-lived tokens for URL-safe SSE) ──────────────

@router.get("/token", summary="Получить короткоживущий токен для SSE")
def get_sse_token(
    teacher: Teacher = Depends(get_current_teacher),
):
    """
    Генерирует токен с коротким TTL (5 минут) для использования в SSE URL.
    Это безопаснее, чем передавать основной JWT в URL.
    """
    from datetime import timedelta
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    token = jwt.encode(
        {"sub": str(teacher.id), "exp": expire, "type": "sse"},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return {"token": token, "expires_in": 300}


# ── Auth через query-параметр (EventSource не поддерживает заголовки) ─────

def _teacher_from_token(token: str, db: Session) -> Teacher:
    try:
        payload    = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        teacher_id = payload.get("sub")
        token_type = payload.get("type")
        if not teacher_id:
            raise ValueError("no sub")
        if token_type not in ("access", "sse"):
            raise ValueError("invalid token type for SSE")
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

    import os as _os
    cors_origin = _os.getenv("CORS_ORIGINS", "http://localhost:3000")
    if "," in cors_origin:
        cors_origin = cors_origin.split(",")[0].strip()

    return StreamingResponse(
        _event_generator(str(lesson_id), queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control":       "no-cache",
            "X-Accel-Buffering":   "no",
            "Connection":          "keep-alive",
            "Access-Control-Allow-Origin": cors_origin,
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


# ── WebSocket для операторского контроля ─────────────────────────────────────

from fastapi import WebSocket, WebSocketDisconnect


@router.websocket("/ws/lessons/{lesson_id}")
async def operator_ws(
    websocket: WebSocket,
    lesson_id: UUID,
    token: str = Query(...),
):
    """
    WebSocket for operator control of active lessons.
    Operator can send commands: pause, resume, skip_step, end.
    Receives real-time lesson events.
    """
    await websocket.accept()

    # Authenticate
    from src.db.base import SessionLocal
    db = SessionLocal()
    try:
        teacher = _teacher_from_token(token, db)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    finally:
        db.close()

    # Verify lesson ownership
    db = SessionLocal()
    try:
        lesson = db.query(Lesson).filter(
            Lesson.id == lesson_id,
            Lesson.teacher_id == teacher.id,
        ).first()
        if not lesson:
            await websocket.close(code=4004, reason="Lesson not found")
            return
    finally:
        db.close()

    # Subscribe to events
    queue = event_bus.subscribe(lesson_id)
    logger.info("[WS] Operator connected to lesson %s", lesson_id)

    import asyncio

    async def receive_commands():
        try:
            while True:
                data = await websocket.receive_json()
                command = data.get("command")
                if command in ("pause", "resume", "skip_step", "end"):
                    event_bus.publish(lesson_id, {
                        "kind": "operator_command",
                        "data": {"command": command, "args": data.get("args", {})},
                    })
                    logger.info("[WS] Operator command: %s for lesson %s", command, lesson_id)
        except WebSocketDisconnect:
            pass

    async def send_events():
        try:
            while True:
                event = await queue.get()
                await websocket.send_json(event)
                if event.get("kind") in ("session_ended", "session_failed"):
                    break
        except Exception:
            pass

    await asyncio.gather(receive_commands(), send_events())
    event_bus.unsubscribe(lesson_id, queue)
