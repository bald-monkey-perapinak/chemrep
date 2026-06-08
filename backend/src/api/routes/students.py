"""
Students API — управление учениками преподавателя.

GET    /api/students          — список учеников
POST   /api/students          — добавить ученика
GET    /api/students/{id}     — профиль ученика с историей уроков
PATCH  /api/students/{id}     — обновить данные
DELETE /api/students/{id}     — удалить ученика
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session, joinedload

from src.db.base import get_db
from src.api.routes.auth import get_current_teacher
from src.models.teacher import Teacher
from src.models.student import Student
from src.models.lesson import Lesson

router = APIRouter(prefix="/students", tags=["students"])


# ── Схемы ─────────────────────────────────────────────────────────────────

class StudentCreate(BaseModel):
    full_name: str = Field(..., min_length=2)
    email:     Optional[EmailStr] = None
    phone:     Optional[str]      = None
    grade:     Optional[int]      = Field(None, ge=1, le=11)
    notes:     Optional[str]      = None

class StudentUpdate(BaseModel):
    full_name: Optional[str]      = None
    email:     Optional[EmailStr] = None
    phone:     Optional[str]      = None
    grade:     Optional[int]      = Field(None, ge=1, le=11)
    notes:     Optional[str]      = None
    is_active: Optional[bool]     = None

class LessonShort(BaseModel):
    id:           str
    scheduled_at: str
    topic_name:   Optional[str]
    status:       str

    class Config:
        from_attributes = True

class StudentOut(BaseModel):
    id:        str
    full_name: str
    email:     Optional[str]
    phone:     Optional[str]
    grade:     Optional[int]
    notes:     Optional[str]
    is_active: bool

    class Config:
        from_attributes = True

class StudentDetail(StudentOut):
    lessons: list[LessonShort] = []


# ── Вспомогательная ───────────────────────────────────────────────────────

def _get_or_404(db: Session, student_id: UUID, teacher: Teacher) -> Student:
    s = db.query(Student).filter(
        Student.id == student_id,
        Student.teacher_id == teacher.id,
    ).first()
    if not s:
        raise HTTPException(404, "Ученик не найден")
    return s


# ── Эндпоинты ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[StudentOut], summary="Список учеников")
def list_students(
    active_only: bool     = True,
    teacher:     Teacher  = Depends(get_current_teacher),
    db:          Session  = Depends(get_db),
):
    q = db.query(Student).filter(Student.teacher_id == teacher.id)
    if active_only:
        q = q.filter(Student.is_active == True)  # noqa: E712
    return q.order_by(Student.full_name).all()


@router.post("", response_model=StudentOut, status_code=201,
             summary="Добавить ученика")
def create_student(
    data:    StudentCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db:      Session = Depends(get_db),
):
    student = Student(teacher_id=teacher.id, **data.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("/{student_id}", response_model=StudentDetail,
            summary="Профиль ученика + история уроков")
def get_student(
    student_id: UUID,
    teacher:    Teacher = Depends(get_current_teacher),
    db:         Session = Depends(get_db),
):
    student = _get_or_404(db, student_id, teacher)
    lessons = (
        db.query(Lesson)
        .filter(Lesson.student_id == student_id)
        .order_by(Lesson.scheduled_at.desc())
        .limit(20)
        .all()
    )

    lesson_shorts = []
    for l in lessons:
        lesson_shorts.append(LessonShort(
            id=str(l.id),
            scheduled_at=l.scheduled_at.isoformat(),
            topic_name=l.topic.name if l.topic else None,
            status=l.status.value,
        ))

    return StudentDetail(
        id=str(student.id),
        full_name=student.full_name,
        email=student.email,
        phone=student.phone,
        grade=student.grade,
        notes=student.notes,
        is_active=student.is_active,
        lessons=lesson_shorts,
    )


@router.patch("/{student_id}", response_model=StudentOut,
              summary="Обновить данные ученика")
def update_student(
    student_id: UUID,
    data:       StudentUpdate,
    teacher:    Teacher = Depends(get_current_teacher),
    db:         Session = Depends(get_db),
):
    student = _get_or_404(db, student_id, teacher)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(student, field, value)
    db.commit()
    db.refresh(student)
    return student


@router.delete("/{student_id}", status_code=204,
               summary="Удалить ученика")
def delete_student(
    student_id: UUID,
    teacher:    Teacher = Depends(get_current_teacher),
    db:         Session = Depends(get_db),
):
    student = _get_or_404(db, student_id, teacher)
    db.delete(student)
    db.commit()
