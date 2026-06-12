"""
Модель занятия.
Занятие — запланированный урок между преподавателем и учеником
с привязкой к теме из базы знаний.
"""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from src.db.base import Base


class LessonStatus(str, enum.Enum):
    SCHEDULED = "scheduled"     # запланировано
    IN_PROGRESS = "in_progress" # идёт прямо сейчас
    COMPLETED = "completed"     # завершено
    CANCELLED = "cancelled"     # отменено
    MISSED = "missed"           # ученик не пришёл


class VCSPlatform(str, enum.Enum):
    ZOOM = "zoom"
    YANDEX = "yandex"
    MEET = "meet"
    WEBRTC = "webrtc"           # собственная комната (на будущее)


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_topics.id", ondelete="SET NULL"), nullable=True)

    # Время
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    duration_min = Column(Integer, default=60)  # длительность в минутах
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    # Конференция
    vcs_platform = Column(Enum(VCSPlatform), nullable=False, default=VCSPlatform.ZOOM)
    vcs_link = Column(String(1000), nullable=True)

    # Статус
    status = Column(Enum(LessonStatus), nullable=False, default=LessonStatus.SCHEDULED)

    # Результат
    transcript = Column(Text, nullable=True)            # текст диалога после урока
    recording_path = Column(String(500), nullable=True) # путь к записи в S3
    homework_sent = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)                 # заметки преподавателя

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    teacher = relationship("Teacher", back_populates="lessons")
    student = relationship("Student", back_populates="lessons")
    topic = relationship("KnowledgeTopic", back_populates="lessons")
    session = relationship("LessonSession", back_populates="lesson", uselist=False)
    homework = relationship("Homework", back_populates="lesson", uselist=False)

    def __repr__(self):
        return f"<Lesson {self.id} at {self.scheduled_at}>"
