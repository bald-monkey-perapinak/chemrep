"""
Embeddings Service — генерация и поиск эмбеддингов через pgvector.

Используетsentence-transformers для генерации эмбеддингов локально (без API).
Хранение и поиск через PostgreSQL + pgvector.

Для работы требуется:
  1. Расширение pgvector в PostgreSQL
  2. Python-пакет sentence-transformers
"""

from __future__ import annotations

import logging
import os
from typing import Optional
from uuid import UUID

import numpy as np

logger = logging.getLogger(__name__)

# Конфигурация
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
EMBEDDING_DIM = 384  # Размерность для paraphrase-multilingual-MiniLM-L12-v2

# Глобальный кэш модели
_model = None


def _get_model():
    """Ленивая загрузка модели sentence-transformers."""
    global _model
    if _model is not None:
        return _model

    try:
        from sentence_transformers import SentenceTransformer
        logger.info("[Embeddings] Загрузка модели %s...", EMBEDDING_MODEL)
        _model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("[Embeddings] Модель загружена (dim=%d)", EMBEDDING_DIM)
        return _model
    except ImportError:
        logger.warning("[Embeddings] sentence-transformers не установлен. "
                       "Установите: pip install sentence-transformers")
        return None
    except Exception as e:
        logger.error("[Embeddings] Ошибка загрузки модели: %s", e)
        return None


def generate_embedding(text: str) -> Optional[list[float]]:
    """
    Сгенерировать эмбеддинг для текста.
    Возвращает вектор размерности EMBEDDING_DIM или None.
    """
    if not text or not text.strip():
        return None

    model = _get_model()
    if model is None:
        return None

    try:
        # Обрезаем длинный текст (модель ограничена 128 токенами)
        truncated = text[:512]
        embedding = model.encode(truncated, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        logger.error("[Embeddings] Ошибка генерации эмбеддинга: %s", e)
        return None


def generate_embeddings_batch(texts: list[str]) -> list[Optional[list[float]]]:
    """Пакетная генерация эмбеддингов."""
    model = _get_model()
    if model is None:
        return [None] * len(texts)

    try:
        truncated = [t[:512] if t else "" for t in texts]
        embeddings = model.encode(truncated, normalize_embeddings=True, batch_size=32)
        return [e.tolist() for e in embeddings]
    except Exception as e:
        logger.error("[Embeddings] Ошибка пакетной генерации: %s", e)
        return [None] * len(texts)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Вычислить cosine similarity между двумя векторами."""
    a_arr = np.array(a)
    b_arr = np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr) + 1e-8))
