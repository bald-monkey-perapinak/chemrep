"""
Sessions API — просмотр диалога и транскриптов урока.

GET  /api/sessions/{lesson_id}               — полная сессия с диалогом
GET  /api/sessions/{lesson_id}/transcript    — транскрипт в виде текста
GET  /api/sessions/{lesson_id}/dialog        — история диалога (JSON)
"""

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from fastapi.responses import PlainTextResponse

from src.db.base import get_db
from src.api.routes.auth import get_current_teacher
from src.models.teacher import Teacher
from src.models.lesson import Lesson
from src.models.session import LessonSession

router = APIRouter(prefix="/sessions", tags=["sessions"])


# ── Схемы ─────────────────────────────────────────────────────────────────

class DialogEntry(BaseModel):
    role: str          # "bot" | "student"
    text: str
    ts:   str

class EventEntry(BaseModel):
    kind: str
    data: dict
    ts:   str

class SessionFull(BaseModel):
    lesson_id:      str
    status:         str
    current_step:   int
    total_steps:    Optional[int]
    bot_joined_at:  Optional[str]
    bot_left_at:    Optional[str]
    error_message:  Optional[str]
    dialog_history: list[DialogEntry]
    event_log:      list[EventEntry]


# ── Хелпер ────────────────────────────────────────────────────────────────

def _get_lesson(db: Session, lesson_id: UUID, teacher: Teacher) -> Lesson:
    lesson = (
        db.query(Lesson)
        .options(joinedload(Lesson.session))
        .filter(Lesson.id == lesson_id, Lesson.teacher_id == teacher.id)
        .first()
    )
    if not lesson:
        raise HTTPException(404, "Занятие не найдено")
    return lesson


# ── Эндпоинты ─────────────────────────────────────────────────────────────

@router.get("/{lesson_id}", response_model=SessionFull,
            summary="Полная сессия бота — диалог и события")
def get_session(
    lesson_id: UUID,
    teacher:   Teacher = Depends(get_current_teacher),
    db:        Session = Depends(get_db),
):
    lesson = _get_lesson(db, lesson_id, teacher)
    s = lesson.session
    if not s:
        raise HTTPException(404, "Сессия ещё не создана")

    return SessionFull(
        lesson_id=str(lesson_id),
        status=s.status.value,
        current_step=s.current_step or 0,
        total_steps=s.total_steps,
        bot_joined_at=s.bot_joined_at.isoformat() if s.bot_joined_at else None,
        bot_left_at=s.bot_left_at.isoformat() if s.bot_left_at else None,
        error_message=s.error_message,
        dialog_history=[DialogEntry(**m) for m in (s.dialog_history or [])],
        event_log=[EventEntry(**e) for e in (s.event_log or [])],
    )


@router.get("/{lesson_id}/transcript", response_class=PlainTextResponse,
            summary="Транскрипт урока как текст")
def get_transcript(
    lesson_id: UUID,
    teacher:   Teacher = Depends(get_current_teacher),
    db:        Session = Depends(get_db),
):
    lesson = _get_lesson(db, lesson_id, teacher)
    if not lesson.transcript:
        raise HTTPException(404, "Транскрипт ещё не готов")
    return lesson.transcript


@router.get("/{lesson_id}/dialog", response_model=list[DialogEntry],
            summary="История диалога (только реплики, без событий)")
def get_dialog(
    lesson_id: UUID,
    teacher:   Teacher = Depends(get_current_teacher),
    db:        Session = Depends(get_db),
):
    lesson = _get_lesson(db, lesson_id, teacher)
    s = lesson.session
    if not s:
        return []
    return [DialogEntry(**m) for m in (s.dialog_history or [])]
