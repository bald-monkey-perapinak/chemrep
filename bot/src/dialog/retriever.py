"""
RAG Retriever — поиск релевантных материалов из базы знаний по вопросу ученика.

Стратегия поиска (без векторной БД, только SQL):
  1. TF-IDF-подобный keyword match по полям topic.keywords, topic.name, topic.description
  2. Полнотекстовый поиск по extracted_text файлов (если текст уже извлечён)
  3. Ограничение scope: только топики текущего урока и его раздела / класса

Результат — список фрагментов текста (chunks), которые передаются в контекст LLM.

Будущее улучшение: заменить keyword match на pgvector + эмбеддинги.
"""

from __future__ import annotations

import logging
import re
import sys
import os
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

_backend = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend"))
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Максимальное количество чанков в контексте LLM
MAX_CHUNKS = 5
# Максимальная длина одного чанка (символов)
MAX_CHUNK_LEN = 800


@dataclass
class RetrievedChunk:
    source: str       # откуда взят чанк: "topic_script" | "file_text" | "topic_meta"
    title: str        # название топика или файла
    text: str         # фрагмент текста
    score: float      # релевантность (0–1, выше — лучше)


class RAGRetriever:
    """
    Ищет релевантные материалы в БД по вопросу ученика.
    Привязан к конкретному уроку (topic_id, teacher_id).
    """

    def __init__(
        self,
        db,  # sqlalchemy Session
        topic_id: UUID,
        teacher_id: UUID,
        max_chunks: int = MAX_CHUNKS,
    ):
        self._db         = db
        self._topic_id   = topic_id
        self._teacher_id = teacher_id
        self._max_chunks = max_chunks
        self._topic: Optional[KnowledgeTopic] = None

    def _get_topic(self):
        if self._topic is None:
            from src.models.knowledge import KnowledgeTopic
            self._topic = self._db.query(KnowledgeTopic).filter(
                KnowledgeTopic.id == self._topic_id
            ).first()
        return self._topic

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        """
        Найти фрагменты, релевантные запросу query.
        Возвращает список чанков, отсортированных по убыванию score.
        """
        if not query.strip():
            return []

        keywords = _extract_keywords(query)
        chunks: list[RetrievedChunk] = []

        # 1. Текущая тема — сценарий урока
        chunks.extend(self._search_current_topic(keywords))

        # 2. Файлы текущей темы с извлечённым текстом
        chunks.extend(self._search_topic_files(self._topic_id, keywords))

        # 3. Смежные темы из того же раздела
        chunks.extend(self._search_sibling_topics(keywords))

        # Дедупликация + сортировка по score
        seen: set[str] = set()
        unique: list[RetrievedChunk] = []
        for c in sorted(chunks, key=lambda x: x.score, reverse=True):
            key = c.text[:80]
            if key not in seen:
                seen.add(key)
                unique.append(c)

        result = unique[: self._max_chunks]
        logger.debug(
            "[RAG] query=%r → %d чанков (из %d кандидатов)",
            query[:50], len(result), len(chunks),
        )
        return result

    def get_topic_context(self) -> str:
        """
        Сформировать базовый контекст урока (без учёта вопроса).
        Используется как системный контекст при инициализации LLM-диалога.
        """
        topic = self._get_topic()
        if not topic:
            return ""

        parts = [f"Тема урока: {topic.name}"]
        if topic.description:
            parts.append(f"Описание: {topic.description}")
        if topic.keywords:
            parts.append(f"Ключевые слова: {topic.keywords}")

        # Добавить первые несколько шагов сценария как краткое содержание
        script = topic.lesson_script or []
        if script:
            summary_steps = [s.get("text", "") for s in script[:3] if s.get("text")]
            if summary_steps:
                parts.append("Краткое содержание урока:\n" + "\n".join(f"— {t}" for t in summary_steps))

        return "\n".join(parts)

    # ── Поиск по текущей теме ──────────────────────────────────────────────

    def _search_current_topic(self, keywords: list[str]) -> list[RetrievedChunk]:
        topic = self._get_topic()
        if not topic:
            return []

        chunks = []

        # Мета-информация темы
        meta_text = " ".join(filter(None, [topic.name, topic.description, topic.keywords]))
        score = _keyword_score(meta_text, keywords)
        if score > 0:
            chunks.append(RetrievedChunk(
                source="topic_meta",
                title=topic.name,
                text=_truncate(meta_text, MAX_CHUNK_LEN),
                score=score * 0.5,  # мета весит меньше реального контента
            ))

        # Шаги сценария
        for step in (topic.lesson_script or []):
            text = step.get("text", "")
            if not text:
                continue
            score = _keyword_score(text, keywords)
            if score > 0:
                chunks.append(RetrievedChunk(
                    source="topic_script",
                    title=f"{topic.name} — шаг {step.get('step', '?')}",
                    text=_truncate(text, MAX_CHUNK_LEN),
                    score=score,
                ))

        return chunks

    # ── Поиск по файлам темы ───────────────────────────────────────────────

    def _search_topic_files(self, topic_id: UUID, keywords: list[str]) -> list[RetrievedChunk]:
        from src.models.knowledge import TopicFile
        files = (
            self._db.query(TopicFile)
            .filter(
                TopicFile.topic_id == topic_id,
                TopicFile.text_extracted == True,  # noqa: E712
                TopicFile.extracted_text.isnot(None),
            )
            .all()
        )

        chunks = []
        for f in files:
            text = f.extracted_text or ""
            # Нарезаем на чанки, ищем по каждому
            for chunk_text in _split_into_chunks(text, MAX_CHUNK_LEN):
                score = _keyword_score(chunk_text, keywords)
                if score > 0:
                    chunks.append(RetrievedChunk(
                        source="file_text",
                        title=f.original_name,
                        text=chunk_text,
                        score=score * 1.2,  # файлы с реальным текстом весят больше
                    ))

        return chunks

    # ── Поиск по смежным темам ────────────────────────────────────────────

    def _search_sibling_topics(self, keywords: list[str]) -> list[RetrievedChunk]:
        topic = self._get_topic()
        if not topic:
            return []

        from src.models.knowledge import KnowledgeTopic
        siblings = (
            self._db.query(KnowledgeTopic)
            .filter(
                KnowledgeTopic.section_id == topic.section_id,
                KnowledgeTopic.id != self._topic_id,
                KnowledgeTopic.is_published == True,  # noqa: E712
            )
            .limit(10)
            .all()
        )

        chunks = []
        for t in siblings:
            meta = " ".join(filter(None, [t.name, t.description, t.keywords]))
            score = _keyword_score(meta, keywords)
            if score > 0.3:  # порог выше — смежные темы берём только при явном совпадении
                chunks.append(RetrievedChunk(
                    source="topic_meta",
                    title=t.name,
                    text=_truncate(meta, MAX_CHUNK_LEN),
                    score=score * 0.4,  # смежные темы весят меньше
                ))

        return chunks


# ──────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────────────────────────────────

def _extract_keywords(text: str) -> list[str]:
    """Извлечь значимые слова из запроса (минимум 3 символа, без стоп-слов)."""
    STOP = {
        "это", "как", "что", "для", "или", "при", "из", "на", "по",
        "и", "в", "а", "но", "то", "же", "мне", "вы", "ты", "он",
        "она", "они", "мы", "не", "да", "нет", "ли", "бы", "за",
        "до", "от", "со", "об", "без", "под", "над", "про", "через",
        "объясни", "расскажи", "скажи", "покажи", "можешь", "можно",
    }
    words = re.findall(r"[а-яёa-z]{3,}", text.lower())
    return [w for w in words if w not in STOP]


def _keyword_score(text: str, keywords: list[str]) -> float:
    """Простая TF-подобная оценка: доля найденных ключевых слов."""
    if not keywords or not text:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw in text_lower)
    return hits / len(keywords)


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "…"


def _split_into_chunks(text: str, chunk_size: int) -> list[str]:
    """Разбить длинный текст на перекрывающиеся чанки."""
    words = text.split()
    result = []
    step = chunk_size // 5   # шаг в символах между чанками (overlap ~20%)
    start = 0
    while start < len(text):
        chunk = text[start: start + chunk_size]
        if chunk.strip():
            result.append(chunk.strip())
        start += step
        if start >= len(text):
            break
    return result or [text[:chunk_size]]
