"""
Модель ученика.
Ученик привязан к конкретному преподавателю.
"""

from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from src.db.base import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)

    # Основные данные
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)          # для отправки ДЗ
    phone = Column(String(50), nullable=True)
    grade = Column(Integer, nullable=True)               # класс: 8, 9, 10, 11

    # Заметки преподавателя об ученике
    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    teacher = relationship("Teacher", back_populates="students")
    lessons = relationship("Lesson", back_populates="student")

    def __repr__(self):
        return f"<Student {self.full_name}>"


class StudentProgress(Base):
    """
    Прогресс ученика между уроками.
    Сохраняет агрегаты и снимок модели ученика после каждого урока.
    """
    __tablename__ = "student_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True)

    # Агрегаты (обновляются после каждого урока)
    total_correct = Column(Integer, default=0)
    total_incorrect = Column(Integer, default=0)
    overall_confidence = Column(Float, default=0.5)

    # Слабые/сильные темы (JSONB)
    weak_topics = Column(JSONB, default=list)
    strong_topics = Column(JSONB, default=list)
    common_errors = Column(JSONB, default=list)

    # Рекомендации для следующего урока
    recommendations = Column(JSONB, default=list)

    # Модель ученика (полный снимок, JSONB)
    student_model_snapshot = Column(JSONB, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    student = relationship("Student")
    lesson = relationship("Lesson")

    def __repr__(self):
        return f"<StudentProgress student={self.student_id}>"
