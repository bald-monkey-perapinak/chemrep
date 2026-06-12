"""
Lessons API — управление занятиями.

GET    /api/lessons                — список занятий (с фильтрами)
POST   /api/lessons                — создать занятие
GET    /api/lessons/{id}           — занятие + сессия + ДЗ
PATCH  /api/lessons/{id}           — обновить занятие
DELETE /api/lessons/{id}           — удалить занятие
GET    /api/lessons/{id}/session   — статус сессии бота (real-time)
PATCH  /api/lessons/{id}/homework  — обновить / создать ДЗ к занятию
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from src.db.base import get_db
from src.api.routes.auth import get_current_teacher
from src.models.teacher import Teacher
from src.models.lesson import Lesson, LessonStatus, VCSPlatform
from src.models.session import LessonSession
from src.models.homework import Homework, HomeworkDeliveryStatus

router = APIRouter(prefix="/lessons", tags=["lessons"])


# ── Схемы ─────────────────────────────────────────────────────────────────

class LessonCreate(BaseModel):
    student_id:   Optional[str]  = None
    topic_id:     Optional[str]  = None
    scheduled_at: datetime
    duration_min: int             = 60
    vcs_platform: str             = "zoom"
    vcs_link:     Optional[str]  = None
    notes:        Optional[str]  = None

class LessonUpdate(BaseModel):
    student_id:   Optional[str]  = None
    topic_id:     Optional[str]  = None
    scheduled_at: Optional[datetime] = None
    vcs_platform: Optional[str]  = None
    vcs_link:     Optional[str]  = None
    notes:        Optional[str]  = None
    status:       Optional[str]  = None

class SessionOut(BaseModel):
    status:        str
    current_step:  int
    total_steps:   Optional[int]
    bot_joined_at: Optional[str]
    bot_left_at:   Optional[str]
    error_message: Optional[str]

class HomeworkIn(BaseModel):
    title:        Optional[str] = None
    description:  Optional[str] = None
    file_path:    Optional[str] = None
    external_url: Optional[str] = None

class HomeworkOut(BaseModel):
    id:               str
    title:            Optional[str]
    description:      Optional[str]
    file_path:        Optional[str]
    external_url:     Optional[str]
    delivery_status:  str
    sent_at:          Optional[str]

class LessonOut(BaseModel):
    id:             str
    student_id:     Optional[str]
    student_name:   Optional[str]
    topic_id:       Optional[str]
    topic_name:     Optional[str]
    scheduled_at:   str
    duration_min:   int
    started_at:     Optional[str]
    finished_at:    Optional[str]
    vcs_platform:   str
    vcs_link:       Optional[str]
    status:         str
    transcript:     Optional[str]
    homework_sent:  bool
    notes:          Optional[str]
    session:        Optional[SessionOut]  = None
    homework:       Optional[HomeworkOut] = None


# ── Хелпер ────────────────────────────────────────────────────────────────

def _get_or_404(db: Session, lesson_id: UUID, teacher: Teacher) -> Lesson:
    lesson = (
        db.query(Lesson)
        .options(
            joinedload(Lesson.student),
            joinedload(Lesson.topic),
            joinedload(Lesson.session),
            joinedload(Lesson.homework),
        )
        .filter(Lesson.id == lesson_id, Lesson.teacher_id == teacher.id)
        .first()
    )
    if not lesson:
        raise HTTPException(404, "Занятие не найдено")
    return lesson


def _lesson_out(l: Lesson) -> LessonOut:
    session_out = None
    if l.session:
        s = l.session
        session_out = SessionOut(
            status=s.status.value,
            current_step=s.current_step or 0,
            total_steps=s.total_steps,
            bot_joined_at=s.bot_joined_at.isoformat() if s.bot_joined_at else None,
            bot_left_at=s.bot_left_at.isoformat() if s.bot_left_at else None,
            error_message=s.error_message,
        )

    hw_out = None
    if l.homework:
        h = l.homework
        hw_out = HomeworkOut(
            id=str(h.id),
            title=h.title,
            description=h.description,
            file_path=h.file_path,
            external_url=h.external_url,
            delivery_status=h.delivery_status.value,
            sent_at=h.sent_at.isoformat() if h.sent_at else None,
        )

    return LessonOut(
        id=str(l.id),
        student_id=str(l.student_id) if l.student_id else None,
        student_name=l.student.full_name if l.student else None,
        topic_id=str(l.topic_id) if l.topic_id else None,
        topic_name=l.topic.name if l.topic else None,
        scheduled_at=l.scheduled_at.isoformat(),
        duration_min=l.duration_min or 60,
        started_at=l.started_at.isoformat() if l.started_at else None,
        finished_at=l.finished_at.isoformat() if l.finished_at else None,
        vcs_platform=l.vcs_platform.value,
        vcs_link=l.vcs_link,
        status=l.status.value,
        transcript=l.transcript,
        homework_sent=l.homework_sent,
        notes=l.notes,
        session=session_out,
        homework=hw_out,
    )


# ── Эндпоинты ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[LessonOut], summary="Список занятий")
def list_lessons(
    status:     Optional[str] = Query(None, description="Фильтр по статусу: scheduled|in_progress|completed|cancelled|missed"),
    student_id: Optional[str] = Query(None),
    from_date:  Optional[datetime] = Query(None),
    to_date:    Optional[datetime] = Query(None),
    limit:      int            = Query(50, le=200),
    teacher:    Teacher        = Depends(get_current_teacher),
    db:         Session        = Depends(get_db),
):
    q = (
        db.query(Lesson)
        .options(joinedload(Lesson.student), joinedload(Lesson.topic),
                 joinedload(Lesson.session), joinedload(Lesson.homework))
        .filter(Lesson.teacher_id == teacher.id)
    )
    if status:
        try:
            q = q.filter(Lesson.status == LessonStatus(status))
        except ValueError:
            raise HTTPException(400, f"Неизвестный статус: {status}")
    if student_id:
        q = q.filter(Lesson.student_id == student_id)
    if from_date:
        q = q.filter(Lesson.scheduled_at >= from_date)
    if to_date:
        q = q.filter(Lesson.scheduled_at <= to_date)

    lessons = q.order_by(Lesson.scheduled_at.desc()).limit(limit).all()
    return [_lesson_out(l) for l in lessons]


@router.post("", response_model=LessonOut, status_code=201,
             summary="Создать занятие")
def create_lesson(
    data:    LessonCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db:      Session = Depends(get_db),
):
    try:
        platform = VCSPlatform(data.vcs_platform)
    except ValueError:
        raise HTTPException(400, f"Неизвестная платформа: {data.vcs_platform}")

    lesson = Lesson(
        teacher_id=teacher.id,
        student_id=data.student_id,
        topic_id=data.topic_id,
        scheduled_at=data.scheduled_at,
        duration_min=data.duration_min,
        vcs_platform=platform,
        vcs_link=data.vcs_link,
        notes=data.notes,
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return _lesson_out(lesson)


@router.get("/{lesson_id}", response_model=LessonOut,
            summary="Занятие с сессией и ДЗ")
def get_lesson(
    lesson_id: UUID,
    teacher:   Teacher = Depends(get_current_teacher),
    db:        Session = Depends(get_db),
):
    return _lesson_out(_get_or_404(db, lesson_id, teacher))


@router.patch("/{lesson_id}", response_model=LessonOut,
              summary="Обновить занятие")
def update_lesson(
    lesson_id: UUID,
    data:      LessonUpdate,
    teacher:   Teacher = Depends(get_current_teacher),
    db:        Session = Depends(get_db),
):
    lesson = _get_or_404(db, lesson_id, teacher)
    fields = data.model_dump(exclude_unset=True)

    if "status" in fields:
        try:
            fields["status"] = LessonStatus(fields["status"])
        except ValueError:
            raise HTTPException(400, f"Неизвестный статус: {fields['status']}")
    if "vcs_platform" in fields:
        try:
            fields["vcs_platform"] = VCSPlatform(fields["vcs_platform"])
        except ValueError:
            raise HTTPException(400, f"Неизвестная платформа: {fields['vcs_platform']}")

    for field, value in fields.items():
        setattr(lesson, field, value)

    db.commit()
    db.refresh(lesson)
    return _lesson_out(lesson)


@router.delete("/{lesson_id}", status_code=204,
               summary="Удалить занятие")
def delete_lesson(
    lesson_id: UUID,
    teacher:   Teacher = Depends(get_current_teacher),
    db:        Session = Depends(get_db),
):
    lesson = _get_or_404(db, lesson_id, teacher)
    db.delete(lesson)
    db.commit()


@router.get("/{lesson_id}/session", response_model=Optional[SessionOut],
            summary="Статус сессии бота (для polling с фронтенда)")
def get_session(
    lesson_id: UUID,
    teacher:   Teacher = Depends(get_current_teacher),
    db:        Session = Depends(get_db),
):
    lesson = _get_or_404(db, lesson_id, teacher)
    if not lesson.session:
        return None
    s = lesson.session
    return SessionOut(
        status=s.status.value,
        current_step=s.current_step or 0,
        total_steps=s.total_steps,
        bot_joined_at=s.bot_joined_at.isoformat() if s.bot_joined_at else None,
        bot_left_at=s.bot_left_at.isoformat() if s.bot_left_at else None,
        error_message=s.error_message,
    )


@router.patch("/{lesson_id}/homework", response_model=HomeworkOut,
              summary="Создать или обновить ДЗ к занятию")
def upsert_homework(
    lesson_id: UUID,
    data:      HomeworkIn,
    teacher:   Teacher = Depends(get_current_teacher),
    db:        Session = Depends(get_db),
):
    lesson = _get_or_404(db, lesson_id, teacher)
    hw = lesson.homework
    if hw is None:
        hw = Homework(lesson_id=lesson_id)
        db.add(hw)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(hw, field, value)

    db.commit()
    db.refresh(hw)
    return HomeworkOut(
        id=str(hw.id),
        title=hw.title,
        description=hw.description,
        file_path=hw.file_path,
        external_url=hw.external_url,
        delivery_status=hw.delivery_status.value,
        sent_at=hw.sent_at.isoformat() if hw.sent_at else None,
    )
