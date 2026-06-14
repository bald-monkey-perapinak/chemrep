"""
Embeddings Service — индексация и поиск эмбеддингов в pgvector.

Индексация:
  - При загрузке файла: текст извлекается → чанкуется → эмбеддинги сохраняются
  - При обновлении темы: lesson_script чанкуется → эмбеддинги обновляются

Поиск:
  - По запросу ученика генерируется эмбеддинг
  - pgvector находит ближайшие чанки через cosine distance
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.embedding import ContentEmbedding
from src.models.knowledge import KnowledgeTopic, TopicFile
from src.utils.embeddings import generate_embedding, generate_embeddings_batch
from src.utils.text_extractor import chunk_text

logger = logging.getLogger(__name__)

MAX_SEARCH_RESULTS = 5


def index_topic_script(db: Session, topic: KnowledgeTopic, teacher_id: UUID) -> int:
    """
    Проиндексировать lesson_script темы.
    Возвращает количество созданных чанков.
    """
    script = topic.lesson_script
    if not script:
        return 0

    texts = [step.get("text", "") for step in script if step.get("text")]
    if not texts:
        return 0

    # Удаляем старые эмбеддинги этого источника
    db.query(ContentEmbedding).filter(
        ContentEmbedding.source_type == "topic_script",
        ContentEmbedding.source_id == topic.id,
    ).delete()

    # Генерируем эмбеддинги
    all_chunks = []
    for idx, text in enumerate(texts):
        chunks = chunk_text(text)
        for ci, chunk in enumerate(chunks):
            all_chunks.append((idx * 100 + ci, chunk))

    if not all_chunks:
        return 0

    embeddings = generate_embeddings_batch([c[1] for c in all_chunks])

    count = 0
    for (chunk_idx, chunk_text_val), embedding in zip(all_chunks, embeddings):
        if embedding is None:
            continue
        emb = ContentEmbedding(
            source_type="topic_script",
            source_id=topic.id,
            chunk_text=chunk_text_val,
            chunk_index=chunk_idx,
            embedding_json=json.dumps(embedding),
            topic_id=topic.id,
            teacher_id=teacher_id,
        )
        try:
            emb.embedding = embedding
        except (AttributeError, TypeError) as e:
            logger.debug("[Embeddings] pgvector column not available: %s", e)
        db.add(emb)
        count += 1

    db.commit()
    logger.info("[Embeddings] Проиндексировано %d чанков lesson_script для темы %s", count, topic.name)
    return count


def index_topic_file(db: Session, file: TopicFile, extracted_text: str, teacher_id: UUID) -> int:
    """
    Проиндексировать текст извлечённого файла.
    Возвращает количество созданных чанков.
    """
    if not extracted_text or not extracted_text.strip():
        return 0

    # Удаляем старые эмбеддинги этого файла
    db.query(ContentEmbedding).filter(
        ContentEmbedding.source_type == "topic_file",
        ContentEmbedding.source_id == file.id,
    ).delete()

    # Разбиваем текст на чанки
    chunks = chunk_text(extracted_text)
    if not chunks:
        return 0

    embeddings = generate_embeddings_batch(chunks)

    count = 0
    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        if embedding is None:
            continue
        emb = ContentEmbedding(
            source_type="topic_file",
            source_id=file.id,
            chunk_text=chunk,
            chunk_index=idx,
            embedding_json=json.dumps(embedding),
            topic_id=file.topic_id,
            teacher_id=teacher_id,
        )
        try:
            emb.embedding = embedding
        except (AttributeError, TypeError) as e:
            logger.debug("[Embeddings] pgvector column not available: %s", e)
        db.add(emb)
        count += 1

    db.commit()
    logger.info("[Embeddings] Проиндексировано %d чанков из файла %s", count, file.original_name)
    return count


def index_topic_meta(db: Session, topic: KnowledgeTopic, teacher_id: UUID) -> int:
    """Проиндексировать метаданные темы (name + description + keywords)."""
    meta_text = " ".join(filter(None, [topic.name, topic.description, topic.keywords]))
    if not meta_text.strip():
        return 0

    # Удаляем старые мета-эмбеддинги
    db.query(ContentEmbedding).filter(
        ContentEmbedding.source_type == "topic_meta",
        ContentEmbedding.source_id == topic.id,
    ).delete()

    embedding = generate_embedding(meta_text)
    if embedding is None:
        return 0

    emb = ContentEmbedding(
        source_type="topic_meta",
        source_id=topic.id,
        chunk_text=meta_text[:512],
        chunk_index=0,
        embedding_json=json.dumps(embedding),
        topic_id=topic.id,
        teacher_id=teacher_id,
    )
    try:
        emb.embedding = embedding
    except (AttributeError, TypeError) as e:
        logger.debug("[Embeddings] pgvector column not available: %s", e)
    db.add(emb)
    db.commit()
    return 1


def reindex_topic(db: Session, topic: KnowledgeTopic, teacher_id: UUID) -> int:
    """Полная переиндексация темы: мета + script + файлы."""
    count = 0
    count += index_topic_meta(db, topic, teacher_id)
    count += index_topic_script(db, topic, teacher_id)

    for file in topic.files:
        if file.text_extracted and file.extracted_text:
            count += index_topic_file(db, file, file.extracted_text, teacher_id)

    logger.info("[Embeddings] Полная переиндексация темы %s: %d чанков", topic.name, count)
    return count


def search_similar(
    db: Session,
    query: str,
    teacher_id: UUID,
    topic_id: Optional[UUID] = None,
    max_results: int = MAX_SEARCH_RESULTS,
) -> list[dict]:
    """
    Поиск похожих чанков по эмбеддингу запроса.
    Использует pgvector cosine distance.
    """
    query_embedding = generate_embedding(query)
    if query_embedding is None:
        return []

    # Пробуем pgvector-запрос
    try:
        from sqlalchemy import text
        sql = text("""
            SELECT
                id, source_type, source_id, chunk_text, chunk_index, topic_id,
                1 - (embedding <=> :query_vec::vector) AS similarity
            FROM content_embeddings
            WHERE teacher_id = :teacher_id
              AND embedding IS NOT NULL
              AND (:topic_id::uuid IS NULL OR topic_id = :topic_id)
            ORDER BY embedding <=> :query_vec::vector
            LIMIT :max_results
        """)
        result = db.execute(sql, {
            "query_vec": str(query_embedding),
            "teacher_id": str(teacher_id),
            "topic_id": str(topic_id) if topic_id else None,
            "max_results": max_results,
        })
        return [
            {
                "id": str(row.id),
                "source_type": row.source_type,
                "source_id": str(row.source_id),
                "chunk_text": row.chunk_text,
                "chunk_index": row.chunk_index,
                "topic_id": str(row.topic_id) if row.topic_id else None,
                "similarity": float(row.similarity),
            }
            for row in result
        ]
    except Exception as e:
        logger.debug("[Embeddings] pgvector запрос не удался (%s), fallback на JSON", e)

    # Fallback: поиск по JSON-эмбеддингам
    return _search_json_fallback(db, query_embedding, teacher_id, topic_id, max_results)


def _search_json_fallback(
    db: Session,
    query_embedding: list[float],
    teacher_id: UUID,
    topic_id: Optional[UUID],
    max_results: int,
) -> list[dict]:
    """Fallback поиск когда pgvector недоступен."""
    import numpy as np

    q = db.query(ContentEmbedding).filter(ContentEmbedding.teacher_id == teacher_id)
    if topic_id:
        q = q.filter(ContentEmbedding.topic_id == topic_id)

    embeddings = q.all()
    results = []

    for emb in embeddings:
        if not emb.embedding_json:
            continue
        try:
            emb_vec = json.loads(emb.embedding_json)
            sim = float(np.dot(query_embedding, emb_vec) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(emb_vec) + 1e-8
            ))
            results.append({
                "id": str(emb.id),
                "source_type": emb.source_type,
                "source_id": str(emb.source_id),
                "chunk_text": emb.chunk_text,
                "chunk_index": emb.chunk_index,
                "topic_id": str(emb.topic_id) if emb.topic_id else None,
                "similarity": sim,
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:max_results]


def delete_embeddings_for_source(db: Session, source_type: str, source_id: UUID) -> None:
    """Удалить все эмбеддинги для конкретного источника."""
    db.query(ContentEmbedding).filter(
        ContentEmbedding.source_type == source_type,
        ContentEmbedding.source_id == source_id,
    ).delete()
    db.commit()
