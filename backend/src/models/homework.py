"""
Модель домашнего задания.
ДЗ привязано к занятию и может быть отправлено ученику по email или в чат ВКС.
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from src.db.base import Base


class HomeworkDeliveryStatus(str, enum.Enum):
    PENDING = "pending"     # ещё не отправлено
    SENT = "sent"           # отправлено
    FAILED = "failed"       # ошибка при отправке


class Homework(Base):
    """Домашнее задание, выданное по итогам урока."""
    __tablename__ = "homeworks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Содержание
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)           # текст задания (озвучивается ботом)
    file_path = Column(String(1000), nullable=True)     # путь к файлу в S3 (PDF, DOCX)
    external_url = Column(String(1000), nullable=True)  # ссылка (Google Docs и т.п.)

    # Доставка
    delivery_status = Column(Enum(HomeworkDeliveryStatus), default=HomeworkDeliveryStatus.PENDING)
    delivery_channel = Column(String(50), nullable=True) # email | vcs_chat
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivery_error = Column(Text, nullable=True)

    # Дедлайн (опционально)
    due_date = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    lesson = relationship("Lesson", back_populates="homework")

    def __repr__(self):
        return f"<Homework lesson={self.lesson_id} status={self.delivery_status}>"
