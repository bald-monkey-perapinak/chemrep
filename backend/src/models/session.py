"""
Модель сессии урока.
Хранит runtime-состояние бота во время активного урока:
на каком шаге остановились, история диалога, события.
"""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from src.db.base import Base


class SessionStatus(str, enum.Enum):
    STARTING = "starting"       # бот запускается, подключается к конференции
    ACTIVE = "active"           # урок идёт
    PAUSED = "paused"           # пауза (преподаватель взял управление)
    FINISHING = "finishing"     # бот завершает урок, отправляет ДЗ
    ENDED = "ended"             # сессия завершена
    FAILED = "failed"           # аварийное завершение


class LessonSession(Base):
    """
    Активная/завершённая сессия бота.
    Создаётся оркестратором в момент запуска и обновляется по ходу урока.
    """
    __tablename__ = "lesson_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, unique=True)

    status = Column(Enum(SessionStatus), nullable=False, default=SessionStatus.STARTING)

    # Прогресс по сценарию
    current_step = Column(Integer, default=0)           # текущий шаг конспекта
    total_steps = Column(Integer, nullable=True)         # всего шагов в конспекте

    # История диалога (список {role, text, timestamp})
    dialog_history = Column(JSONB, default=list)

    # Лог событий (шаги, вопросы, действия на доске)
    event_log = Column(JSONB, default=list)

    # Сводка урока (JSONB — LessonSummary.to_dict())
    summary = Column(JSONB, nullable=True)

    # Технические метрики
    bot_joined_at = Column(DateTime(timezone=True), nullable=True)
    bot_left_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)          # если status = failed

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    lesson = relationship("Lesson", back_populates="session")

    def __repr__(self):
        return f"<LessonSession lesson={self.lesson_id} status={self.status}>"
