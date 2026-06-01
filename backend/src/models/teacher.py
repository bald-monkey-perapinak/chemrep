"""
Модель преподавателя.
Преподаватель — основной пользователь системы.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from src.db.base import Base


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Авторизация
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)

    # Профиль
    full_name = Column(String(255), nullable=False)
    subject = Column(String(100), default="Химия")

    # Голосовой профиль (путь к файлу модели в S3)
    voice_model_path = Column(String(500), nullable=True)
    voice_model_ready = Column(Boolean, default=False)

    # Настройки по умолчанию
    default_vcs_platform = Column(String(50), default="zoom")  # zoom | yandex

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    students = relationship("Student", back_populates="teacher", cascade="all, delete-orphan")
    lessons = relationship("Lesson", back_populates="teacher", cascade="all, delete-orphan")
    knowledge_classes = relationship("KnowledgeClass", back_populates="teacher", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Teacher {self.email}>"
