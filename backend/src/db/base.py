"""
Базовая конфигурация SQLAlchemy.
Все модели импортируются здесь, чтобы Alembic видел их при генерации миграций.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://chemrep:password@localhost:5432/chemrep"
)

engine = create_engine(DATABASE_URL, poolclass=NullPool)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency для FastAPI — открывает и закрывает сессию на каждый запрос."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Импортируем все модели, чтобы Alembic их видел
from src.models.teacher import Teacher          # noqa
from src.models.student import Student          # noqa
from src.models.lesson import Lesson            # noqa
from src.models.knowledge import (              # noqa
    KnowledgeClass,
    KnowledgeSection,
    KnowledgeTopic,
    TopicFile,
)
from src.models.session import LessonSession    # noqa
from src.models.homework import Homework        # noqa
