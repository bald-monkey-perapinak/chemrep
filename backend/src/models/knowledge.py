"""
Модели базы знаний.
Иерархия: KnowledgeClass → KnowledgeSection → KnowledgeTopic → TopicFile
Пример:   10 класс → Органическая химия → Алканы → [конспект.pdf, задания.pdf]
"""

from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text, Boolean, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from src.db.base import Base


class KnowledgeClass(Base):
    """Класс / год обучения (8, 9, 10, 11)."""
    __tablename__ = "knowledge_classes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(100), nullable=False)          # "10 класс"
    grade_number = Column(Integer, nullable=True)        # 10
    sort_order = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    teacher = relationship("Teacher", back_populates="knowledge_classes")
    sections = relationship("KnowledgeSection", back_populates="knowledge_class", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<KnowledgeClass {self.name}>"


class KnowledgeSection(Base):
    """Раздел внутри класса (Органическая химия, Неорганическая химия)."""
    __tablename__ = "knowledge_sections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_classes.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    knowledge_class = relationship("KnowledgeClass", back_populates="sections")
    topics = relationship("KnowledgeTopic", back_populates="section", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<KnowledgeSection {self.name}>"


class KnowledgeTopic(Base):
    """
    Тема урока (Алканы, Реакции замещения).
    Содержит сценарий урока в виде JSON-шагов и ссылку на доску Miro.
    """
    __tablename__ = "knowledge_topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_sections.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    keywords = Column(String(500), nullable=True)       # для поиска через RAG

    # Сценарий урока: список шагов в JSON
    # Пример: [{"step": 1, "text": "Алканы — это...", "board_commands": [...]}, ...]
    lesson_script = Column(JSONB, nullable=True)

    # Метаданные
    estimated_duration_min = Column(Integer, default=45)  # примерная длительность в минутах
    sort_order = Column(Integer, default=0)
    is_published = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    section = relationship("KnowledgeSection", back_populates="topics")
    files = relationship("TopicFile", back_populates="topic", cascade="all, delete-orphan")
    assets = relationship("TopicAsset", back_populates="topic", cascade="all, delete-orphan")
    lessons = relationship("Lesson", back_populates="topic")

    def __repr__(self):
        return f"<KnowledgeTopic {self.name}>"


class TopicFile(Base):
    """
    Файл, прикреплённый к теме (конспект, задания, схемы).
    Сам файл хранится в S3, здесь только метаданные.
    """
    __tablename__ = "topic_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_topics.id", ondelete="CASCADE"), nullable=False)

    # Метаданные файла
    original_name = Column(String(500), nullable=False)  # имя как загрузил пользователь
    storage_path = Column(String(1000), nullable=False)  # путь в S3
    mime_type = Column(String(100), nullable=True)        # application/pdf, image/png …
    size_bytes = Column(BigInteger, nullable=True)

    # Тип файла в контексте урока
    file_role = Column(String(50), default="material")   # material | homework | image | other

    # Извлечённый текст для RAG-поиска (заполняется асинхронно после загрузки)
    extracted_text = Column(Text, nullable=True)
    text_extracted = Column(Boolean, default=False)

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    topic = relationship("KnowledgeTopic", back_populates="files")

    def __repr__(self):
        return f"<TopicFile {self.original_name}>"


class TopicAsset(Base):
    """
    Ассет для доски: SVG-механизмы реакций, изображения формул.
    """
    __tablename__ = "topic_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_topics.id", ondelete="CASCADE"), nullable=False)

    original_name = Column(String(500), nullable=False)
    storage_path = Column(String(1000), nullable=False)
    mime_type = Column(String(100), nullable=True)
    asset_type = Column(String(50), default="svg")  # svg | image | other

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    topic = relationship("KnowledgeTopic", back_populates="assets")

    def __repr__(self):
        return f"<TopicAsset {self.original_name}>"
