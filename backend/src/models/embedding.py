"""
Модель эмбеддинга для pgvector.

Хранит векторные представления текстовых чанков из базы знаний
для семантического поиска через RAG.
"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from src.db.base import Base


class ContentEmbedding(Base):
    """Эмбеддинг текстового чанка для семантического поиска."""
    __tablename__ = "content_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Привязка к источнику
    source_type = Column(String(50), nullable=False)  # "topic" | "topic_file" | "topic_script"
    source_id = Column(UUID(as_uuid=True), nullable=False)  # ID темы или файла

    # Текстовый чанк
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, default=0)  # порядковый номер чанка в источнике

    # Векторное представление (pgvector)
    # В SQLAlchemy определяется через column_type через migrate
    # Здесь хранится как JSON-массив для совместимости без pgvector
    embedding_json = Column(Text, nullable=True)  # JSON-массив float

    # Метаданные
    topic_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_topics.id", ondelete="CASCADE"), nullable=True)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    topic = relationship("KnowledgeTopic", backref="embeddings")
    teacher = relationship("Teacher", backref="content_embeddings")

    def __repr__(self):
        return f"<ContentEmbedding {self.source_type}:{self.source_id} chunk={self.chunk_index}>"
