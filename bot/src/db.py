"""
Подключение к базе данных для бота.
Бот использует те же модели и ту же БД, что и backend.
"""

import sys
import os

# Добавляем backend в путь, чтобы переиспользовать его модели
_backend = os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from config.settings import config

engine = create_engine(
    config.database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,   # проверять соединение перед выдачей из пула
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_session() -> Session:
    """Контекстный менеджер — гарантирует закрытие сессии."""
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
