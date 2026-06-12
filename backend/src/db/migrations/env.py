"""Alembic environment — подключает все модели и генерирует миграции."""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

# Добавляем корень backend/ в sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.db.base import Base  # noqa

# Импортируем все модели, чтобы Alembic видел их при генерации миграций
from src.models.teacher import Teacher          # noqa
from src.models.student import Student          # noqa
from src.models.lesson import Lesson            # noqa
from src.models.knowledge import (              # noqa
    KnowledgeClass,
    KnowledgeSection,
    KnowledgeTopic,
    TopicFile,
    TopicAsset,
)
from src.models.session import LessonSession    # noqa
from src.models.homework import Homework        # noqa
from src.models.embedding import ContentEmbedding  # noqa

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# DATABASE_URL из переменной окружения имеет приоритет над alembic.ini
database_url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
