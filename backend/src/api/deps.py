"""
Заглушка аутентификации.
Пока auth API не реализован, все запросы считаются от первого преподавателя в базе.
Когда будет реализован auth — заменить get_current_teacher на JWT-валидацию.
"""

from uuid import UUID
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from src.db.base import get_db
from src.models.teacher import Teacher


async def get_current_teacher(
    db: Session = Depends(get_db),
    x_teacher_id: str | None = Header(default=None, description="UUID преподавателя (временно, вместо JWT)"),
) -> Teacher:
    """
    Временная зависимость: берёт UUID из заголовка X-Teacher-Id.
    Если заголовок не передан — возвращает первого преподавателя в базе (удобно для разработки).
    """
    if x_teacher_id:
        try:
            tid = UUID(x_teacher_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат X-Teacher-Id")
        teacher = db.query(Teacher).filter(Teacher.id == tid, Teacher.is_active == True).first()  # noqa: E712
        if not teacher:
            raise HTTPException(status_code=401, detail="Преподаватель не найден")
        return teacher

    # Фоллбэк для разработки
    teacher = db.query(Teacher).filter(Teacher.is_active == True).first()  # noqa: E712
    if not teacher:
        raise HTTPException(status_code=401, detail="В базе нет ни одного преподавателя. Запустите seed_demo.py")
    return teacher
