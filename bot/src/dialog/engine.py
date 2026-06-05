"""
LLM Dialog Engine — диалоговый движок на базе Claude API.

Отвечает за:
  1. Формирование system prompt с контекстом урока и найденными RAG-фрагментами
  2. Ведение истории диалога (messages list для Claude API)
  3. Генерацию ответов на вопросы ученика
  4. Оценку понимания ученика и адаптацию объяснений
  5. Контроль выхода за рамки темы

Режимы работы:
  - Реальный: Claude API (ANTHROPIC_API_KEY задан)
  - Заглушка: StubDialogEngine (LLM_STUB_MODE=true или нет ключа)
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import httpx

from src.dialog.retriever import RAGRetriever, RetrievedChunk

logger = logging.getLogger(__name__)

# Модель Claude для диалога (быстрая, низкая задержка)
CLAUDE_MODEL    = "claude-haiku-4-5-20251001"
MAX_TOKENS      = 300    # ответы должны быть краткими — бот говорит голосом
API_URL         = "https://api.anthropic.com/v1/messages"
API_VERSION     = "2023-06-01"

# Системный промпт — роль и правила поведения бота
SYSTEM_PROMPT_TEMPLATE = """\
Ты — голосовой ассистент-репетитор по химии. Ты ведёшь урок вместо преподавателя.

КОНТЕКСТ УРОКА:
{topic_context}

ПРАВИЛА:
1. Отвечай кратко и чётко — не более 3–4 предложений, ответ будет озвучен голосом.
2. Используй простой язык, подходящий для школьника.
3. Если вопрос не по теме урока — мягко верни к теме.
4. Если ученик не понял — объясни иначе, с примером или аналогией.
5. Никогда не говори, что ты ИИ или языковая модель.
6. Поощряй ученика, если он отвечает правильно.
7. Не придумывай факты — опирайся только на контекст урока.

Отвечай только на русском языке.
"""


# ──────────────────────────────────────────────────────────────────────────
# Типы данных
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class DialogMessage:
    role: str    # "user" | "assistant"
    text: str


@dataclass
class DialogResponse:
    text: str                          # текст для озвучки
    used_chunks: list[RetrievedChunk] = field(default_factory=list)
    tokens_used: int = 0


# ──────────────────────────────────────────────────────────────────────────
# Абстрактный интерфейс
# ──────────────────────────────────────────────────────────────────────────

class BaseDialogEngine(ABC):

    @abstractmethod
    async def respond(self, student_text: str) -> DialogResponse:
        """Сгенерировать ответ на реплику ученика."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Освободить ресурсы."""
        ...

    def get_history(self) -> list[DialogMessage]:
        return []


# ──────────────────────────────────────────────────────────────────────────
# Заглушка
# ──────────────────────────────────────────────────────────────────────────

class StubDialogEngine(BaseDialogEngine):
    """Возвращает фиксированные ответы — для тестов и LLM_STUB_MODE=true."""

    RESPONSES = [
        "Хороший вопрос! Давай разберём это подробнее.",
        "Именно так. Ты на правильном пути.",
        "Попробуй подумать об этом с другой стороны.",
        "Верно подмечено. Продолжаем.",
    ]
    _idx = 0

    async def respond(self, student_text: str) -> DialogResponse:
        text = self.RESPONSES[self._idx % len(self.RESPONSES)]
        self._idx += 1
        logger.debug("[LLM-stub] respond: %r → %r", student_text[:40], text)
        return DialogResponse(text=text)

    async def close(self) -> None:
        pass


# ──────────────────────────────────────────────────────────────────────────
# Claude API
# ──────────────────────────────────────────────────────────────────────────

class ClaudeDialogEngine(BaseDialogEngine):
    """
    Диалоговый движок на Claude API с RAG-контекстом.

    История диалога хранится в памяти (self._history) и передаётся
    в каждый запрос — Claude не хранит состояние между вызовами.
    """

    def __init__(
        self,
        api_key: str,
        retriever: RAGRetriever,
        topic_context: str,
        max_history_turns: int = 10,
    ):
        self._api_key    = api_key
        self._retriever  = retriever
        self._history:   list[DialogMessage] = []
        self._max_turns  = max_history_turns
        self._system     = SYSTEM_PROMPT_TEMPLATE.format(topic_context=topic_context)
        self._client     = httpx.AsyncClient(
            headers={
                "x-api-key":         api_key,
                "anthropic-version": API_VERSION,
                "content-type":      "application/json",
            },
            timeout=20.0,
        )

    async def respond(self, student_text: str) -> DialogResponse:
        # 1. Найти релевантные чанки RAG
        chunks = self._retriever.retrieve(student_text)

        # 2. Собрать RAG-контекст как часть пользовательского сообщения
        rag_block = _format_rag_context(chunks)
        user_content = student_text
        if rag_block:
            user_content = f"{student_text}\n\n[Контекст из базы знаний]\n{rag_block}"

        # 3. Добавить реплику ученика в историю
        self._history.append(DialogMessage(role="user", text=student_text))

        # 4. Сформировать messages для API (только последние N пар)
        messages = _build_messages(self._history, self._max_turns, rag_block)

        # 5. Вызов Claude API
        try:
            resp = await self._client.post(
                API_URL,
                json={
                    "model":      CLAUDE_MODEL,
                    "max_tokens": MAX_TOKENS,
                    "system":     self._system,
                    "messages":   messages,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("[LLM] HTTP %s: %s", e.response.status_code, e.response.text[:300])
            return DialogResponse(text="Позволь секунду подумать... Можешь повторить вопрос?")
        except Exception as e:
            logger.error("[LLM] Ошибка запроса: %s", e)
            return DialogResponse(text="Не расслышал. Повтори, пожалуйста.")

        # 6. Извлечь текст ответа
        reply_text = _extract_reply(data)
        tokens     = data.get("usage", {}).get("output_tokens", 0)

        logger.info("[LLM] Ответ (%d токенов): %s", tokens, reply_text[:80])

        # 7. Добавить ответ бота в историю
        self._history.append(DialogMessage(role="assistant", text=reply_text))

        return DialogResponse(
            text=reply_text,
            used_chunks=chunks,
            tokens_used=tokens,
        )

    def get_history(self) -> list[DialogMessage]:
        return list(self._history)

    async def close(self) -> None:
        await self._client.aclose()


# ──────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────────────────────────────────

def _format_rag_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return ""
    parts = []
    for c in chunks:
        parts.append(f"[{c.title}]\n{c.text}")
    return "\n\n".join(parts)


def _build_messages(
    history: list[DialogMessage],
    max_turns: int,
    rag_block: str,
) -> list[dict]:
    """
    Строим messages для Claude API.
    Берём последние max_turns пар (user+assistant).
    В последнее user-сообщение вставляем RAG-контекст.
    """
    # Берём последние max_turns*2 сообщений (пары user/assistant)
    recent = history[-(max_turns * 2):]

    messages = []
    for i, msg in enumerate(recent):
        # В последнее user-сообщение добавляем RAG
        is_last = i == len(recent) - 1
        if msg.role == "user" and is_last and rag_block:
            content = f"{msg.text}\n\n[Контекст из базы знаний]\n{rag_block}"
        else:
            content = msg.text
        messages.append({"role": msg.role, "content": content})

    return messages


def _extract_reply(data: dict) -> str:
    """Извлечь текст из ответа Claude API."""
    try:
        blocks = data.get("content", [])
        texts  = [b["text"] for b in blocks if b.get("type") == "text"]
        return " ".join(texts).strip() or "Не могу ответить на этот вопрос."
    except Exception:
        return "Давай продолжим урок."


# ──────────────────────────────────────────────────────────────────────────
# Фабрика
# ──────────────────────────────────────────────────────────────────────────

def make_dialog_engine(
    retriever: RAGRetriever,
    topic_context: str,
) -> BaseDialogEngine:
    """
    Выбирает реализацию:
      LLM_STUB_MODE=true или нет ANTHROPIC_API_KEY → StubDialogEngine
      иначе → ClaudeDialogEngine
    """
    if os.getenv("LLM_STUB_MODE", "false").lower() == "true":
        logger.info("[LLM] stub-режим (LLM_STUB_MODE=true)")
        return StubDialogEngine()

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("[LLM] ANTHROPIC_API_KEY не задан — используем заглушку")
        return StubDialogEngine()

    logger.info("[LLM] Claude API (модель=%s)", CLAUDE_MODEL)
    return ClaudeDialogEngine(
        api_key=api_key,
        retriever=retriever,
        topic_context=topic_context,
    )
