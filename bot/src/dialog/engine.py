"""
LLM Dialog Engine — гибридный диалоговый движок.

Стратегия (оптимизация цена/качество):
  1. Шаблонные ответы для базовых фраз — $0
  2. Gemini Flash для большинства вопросов — $0.01/урок
  3. DeepSeek для сложных вопросов — $0.02/урок
  4. Claude Haiku (опционально) — $0.10/урок

Режимы работы:
  - LLM_STUB_MODE=true → StubDialogEngine
  - GEMINI_API_KEY задан → GeminiFlashEngine (приоритет)
  - DEEPSEEK_API_KEY задан → DeepSeekEngine
  - ANTHROPIC_API_KEY задан → ClaudeDialogEngine
  - нет ключей → TemplateDialogEngine (шаблоны)
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import httpx

from src.dialog.retriever import RAGRetriever, RetrievedChunk

logger = logging.getLogger(__name__)

MAX_TOKENS = 800

# ──────────────────────────────────────────────────────────────────────────
# Шаблонные ответы для базовых фраз ($0)
# ──────────────────────────────────────────────────────────────────────────

TEMPLATE_RESPONSES = {
    "greeting": [
        "Здравствуйте! Рада тебя видеть.",
        "Привет! Как дела?",
    ],
    "positive": [
        "Отлично! Молодец!",
        "Правильно! Ты на правильном пути.",
        "Именно так! Запомни это.",
        "Верно! Как ты к этому пришёл?",
    ],
    "encouragement": [
        "Хороший вопрос! Давай разберёмся.",
        "Не переживай, это нормально. Продолжаем.",
        "Ты близко! Давай попробуем ещё раз.",
    ],
    "transition": [
        "Хорошо, двигаемся дальше.",
        "Продолжаем наш урок.",
        "Теперь давай посмотрим на следующее.",
    ],
    "closing": [
        "Отлично! Урок завершён. Если остались вопросы — задавай.",
        "Молодец! Сегодня мы многое разобрали.",
    ],
}

# Паттерны для определения типа фразы
GREETING_PATTERNS = ["привет", "здравствуй", "добрый", "день", "вечер"]
POSITIVE_PATTERNS = ["да", "понял", "ясно", "ага", "угу", "точно", "понятно", "спасибо"]
ENCOURAGEMENT_PATTERNS = ["не знаю", "не понял", "сложно", "не получается", "объясни"]
TRANSITION_PATTERNS = ["продолжай", "давай", "идём", "далее", "следующий"]
CLOSING_PATTERNS = ["пока", "до свидания", "всё", "закончили", "хватит"]


def _detect_template_type(text: str) -> Optional[str]:
    """Определить тип шаблонной фразы."""
    text_lower = text.lower().strip()

    for pattern in GREETING_PATTERNS:
        if pattern in text_lower:
            return "greeting"

    for pattern in POSITIVE_PATTERNS:
        if text_lower.startswith(pattern) or text_lower == pattern:
            return "positive"

    for pattern in ENCOURAGEMENT_PATTERNS:
        if pattern in text_lower:
            return "encouragement"

    for pattern in TRANSITION_PATTERNS:
        if text_lower.startswith(pattern):
            return "transition"

    for pattern in CLOSING_PATTERNS:
        if text_lower.startswith(pattern):
            return "closing"

    return None


def _get_template_response(text: str) -> Optional[str]:
    """Получить шаблонный ответ если фраза типовая."""
    template_type = _detect_template_type(text)
    if template_type and template_type in TEMPLATE_RESPONSES:
        return random.choice(TEMPLATE_RESPONSES[template_type])
    return None


# ──────────────────────────────────────────────────────────────────────────
# Системный промпт
# ──────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """\
Ты — Алина, репетитор по химии для школьников 8–11 классов. Ты ведёшь онлайн-урок через видеоконференцию.

## Личность
- Тебе 28 лет, окончила МХТИ с красным дипломом
- Преподаёшь химию 5 лет
- Добрая, терпеливая, но требовательная
- Говоришь живым языком, с примерами из жизни

## Правила
- Отвечай кратко (2-4 предложения)
- Говори только на русском
- Никогда не говори что ты ИИ
- Если не уверен — скажи «Давай проверим»
- Хвали за правильные ответы, направляй при ошибках

## Контекст урока
{topic_context}
"""


# ──────────────────────────────────────────────────────────────────────────
# Типы данных
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class DialogMessage:
    role: str
    text: str


@dataclass
class DialogResponse:
    text: str
    used_chunks: list[RetrievedChunk] = field(default_factory=list)
    tokens_used: int = 0


# ──────────────────────────────────────────────────────────────────────────
# Абстрактный интерфейс
# ──────────────────────────────────────────────────────────────────────────

class BaseDialogEngine(ABC):

    @abstractmethod
    async def respond(self, student_text: str) -> DialogResponse:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

    def get_history(self) -> list[DialogMessage]:
        return []


# ──────────────────────────────────────────────────────────────────────────
# Шаблонный движок ($0)
# ──────────────────────────────────────────────────────────────────────────

class TemplateDialogEngine(BaseDialogEngine):
    """Ответы на основе шаблонов — для простых фраз без API."""

    def __init__(self, retriever: Optional[RAGRetriever] = None):
        self._retriever = retriever
        self._history: list[DialogMessage] = []

    async def respond(self, student_text: str) -> DialogResponse:
        self._history.append(DialogMessage(role="user", text=student_text))

        # Проверяем шаблон
        template = _get_template_response(student_text)
        if template:
            self._history.append(DialogMessage(role="assistant", text=template))
            return DialogResponse(text=template)

        # Если не шаблон — ищем в RAG и даём базовый ответ
        chunks = []
        if self._retriever:
            chunks = self._retriever.retrieve(student_text)

        if chunks:
            text = f"Хороший вопрос! Давай разберём. {chunks[0].text[:200]}"
        else:
            text = "Интересный вопрос! Давай вернёмся к теме урока."

        self._history.append(DialogMessage(role="assistant", text=text))
        return DialogResponse(text=text, used_chunks=chunks)

    async def close(self) -> None:
        pass

    def get_history(self) -> list[DialogMessage]:
        return list(self._history)


# ──────────────────────────────────────────────────────────────────────────
# Stub
# ──────────────────────────────────────────────────────────────────────────

class StubDialogEngine(BaseDialogEngine):
    """Заглушка для тестов."""

    RESPONSES = [
        "Хороший вопрос! Давай разберём это подробнее.",
        "Именно так. Ты на правильном пути.",
        "Попробуй подумать об этом с другой стороны.",
        "Верно подмечено. Продолжаем.",
    ]

    def __init__(self, retriever=None):
        self._retriever = retriever
        self._history: list[DialogMessage] = []
        self._idx = 0

    async def respond(self, student_text: str) -> DialogResponse:
        text = self.RESPONSES[self._idx % len(self.RESPONSES)]
        self._idx += 1
        self._history.append(DialogMessage(role="user", text=student_text))
        self._history.append(DialogMessage(role="assistant", text=text))
        return DialogResponse(text=text)

    async def close(self) -> None:
        pass


# ──────────────────────────────────────────────────────────────────────────
# Gemini Flash — основной LLM ($0.01/урок)
# ──────────────────────────────────────────────────────────────────────────

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_MODEL = "gemini-2.0-flash"


class GeminiFlashEngine(BaseDialogEngine):
    """Движок на Gemini Flash — быстрый и дешёвый."""

    def __init__(
        self,
        api_key: str,
        retriever: RAGRetriever,
        topic_context: str,
    ):
        self._api_key = api_key
        self._retriever = retriever
        self._history: list[DialogMessage] = []
        self._system = SYSTEM_PROMPT_TEMPLATE.format(topic_context=topic_context)
        self._client = httpx.AsyncClient(timeout=15.0)

    async def respond(self, student_text: str) -> DialogResponse:
        # 1. Шаблонный ответ?
        template = _get_template_response(student_text)
        if template:
            self._history.append(DialogMessage(role="user", text=student_text))
            self._history.append(DialogMessage(role="assistant", text=template))
            return DialogResponse(text=template)

        # 2. RAG поиск
        chunks = self._retriever.retrieve(student_text) if self._retriever else []
        rag_block = _format_rag_context(chunks)

        user_content = student_text
        if rag_block:
            user_content = f"{student_text}\n\n[Контекст]\n{rag_block}"

        self._history.append(DialogMessage(role="user", text=student_text))

        # 3. Формируем промпт
        recent = self._history[-10:]
        contents = []
        for msg in recent:
            role = "user" if msg.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg.text}]})

        # 4. Запрос к Gemini
        url = GEMINI_API_URL.format(model=GEMINI_MODEL)
        payload = {
            "system_instruction": {"parts": [{"text": self._system}]},
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": MAX_TOKENS,
                "temperature": 0.7,
            },
        }

        try:
            resp = await self._client.post(
                url,
                params={"key": self._api_key},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error("[Gemini] Ошибка: %s", e)
            return DialogResponse(text="Позволь секунду подумать...")

        # 5. Извлекаем ответ
        reply_text = _extract_gemini_reply(data)
        self._history.append(DialogMessage(role="assistant", text=reply_text))

        logger.info("[Gemini] Ответ: %s", reply_text[:80])
        return DialogResponse(text=reply_text, used_chunks=chunks)

    async def close(self) -> None:
        await self._client.aclose()

    def get_history(self) -> list[DialogMessage]:
        return list(self._history)


def _extract_gemini_reply(data: dict) -> str:
    """Извлечь текст из ответа Gemini API."""
    try:
        candidates = data.get("candidates", [])
        if not candidates:
            return "Не могу ответить."
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        texts = [p.get("text", "") for p in parts if "text" in p]
        return " ".join(texts).strip() or "Давай продолжим урок."
    except Exception:
        return "Давай продолжим урок."


# ──────────────────────────────────────────────────────────────────────────
# DeepSeek — для сложных вопросов ($0.02/урок)
# ──────────────────────────────────────────────────────────────────────────

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"


class DeepSeekEngine(BaseDialogEngine):
    """Движок на DeepSeek — высокое качество для сложных вопросов."""

    def __init__(
        self,
        api_key: str,
        retriever: RAGRetriever,
        topic_context: str,
    ):
        self._api_key = api_key
        self._retriever = retriever
        self._history: list[DialogMessage] = []
        self._system = SYSTEM_PROMPT_TEMPLATE.format(topic_context=topic_context)
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=20.0,
        )

    async def respond(self, student_text: str) -> DialogResponse:
        # Шаблонный ответ?
        template = _get_template_response(student_text)
        if template:
            self._history.append(DialogMessage(role="user", text=student_text))
            self._history.append(DialogMessage(role="assistant", text=template))
            return DialogResponse(text=template)

        # RAG поиск
        chunks = self._retriever.retrieve(student_text) if self._retriever else []
        rag_block = _format_rag_context(chunks)

        user_content = student_text
        if rag_block:
            user_content = f"{student_text}\n\n[Контекст]\n{rag_block}"

        self._history.append(DialogMessage(role="user", text=student_text))

        # Формируем messages
        messages = [{"role": "system", "content": self._system}]
        for msg in self._history[-10:]:
            messages.append({"role": msg.role, "content": msg.text})

        # Запрос к DeepSeek
        try:
            resp = await self._client.post(
                DEEPSEEK_API_URL,
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": messages,
                    "max_tokens": MAX_TOKENS,
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error("[DeepSeek] Ошибка: %s", e)
            return DialogResponse(text="Позволь секунду подумать...")

        # Извлекаем ответ
        reply_text = data["choices"][0]["message"]["content"]
        self._history.append(DialogMessage(role="assistant", text=reply_text))

        tokens = data.get("usage", {}).get("total_tokens", 0)
        logger.info("[DeepSeek] Ответ (%d токенов): %s", tokens, reply_text[:80])

        return DialogResponse(text=reply_text, used_chunks=chunks, tokens_used=tokens)

    async def close(self) -> None:
        await self._client.aclose()

    def get_history(self) -> list[DialogMessage]:
        return list(self._history)


# ──────────────────────────────────────────────────────────────────────────
# Claude API — опционально ($0.10/урок)
# ──────────────────────────────────────────────────────────────────────────

CLAUDE_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_API_VERSION = "2023-06-01"


class ClaudeDialogEngine(BaseDialogEngine):
    """Движок на Claude — опционально для максимального качества."""

    def __init__(
        self,
        api_key: str,
        retriever: RAGRetriever,
        topic_context: str,
        max_history_turns: int = 10,
    ):
        self._api_key = api_key
        self._retriever = retriever
        self._history: list[DialogMessage] = []
        self._max_turns = max_history_turns
        self._system = SYSTEM_PROMPT_TEMPLATE.format(topic_context=topic_context)
        self._client = httpx.AsyncClient(
            headers={
                "x-api-key": api_key,
                "anthropic-version": CLAUDE_API_VERSION,
                "Content-Type": "application/json",
            },
            timeout=20.0,
        )

    async def respond(self, student_text: str) -> DialogResponse:
        # Шаблонный ответ?
        template = _get_template_response(student_text)
        if template:
            self._history.append(DialogMessage(role="user", text=student_text))
            self._history.append(DialogMessage(role="assistant", text=template))
            return DialogResponse(text=template)

        # RAG поиск
        chunks = self._retriever.retrieve(student_text) if self._retriever else []
        rag_block = _format_rag_context(chunks)

        user_content = student_text
        if rag_block:
            user_content = f"{student_text}\n\n[Контекст]\n{rag_block}"

        self._history.append(DialogMessage(role="user", text=student_text))

        # Формируем messages
        recent = self._history[-(self._max_turns * 2):]
        messages = []
        for i, msg in enumerate(recent):
            is_last = i == len(recent) - 1
            if msg.role == "user" and is_last and rag_block:
                content = f"{msg.text}\n\n[Контекст]\n{rag_block}"
            else:
                content = msg.text
            messages.append({"role": msg.role, "content": content})

        # Запрос к Claude
        try:
            resp = await self._client.post(
                CLAUDE_API_URL,
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": MAX_TOKENS,
                    "system": self._system,
                    "messages": messages,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error("[Claude] Ошибка: %s", e)
            return DialogResponse(text="Позволь секунду подумать...")

        # Извлекаем ответ
        blocks = data.get("content", [])
        texts = [b["text"] for b in blocks if b.get("type") == "text"]
        reply_text = " ".join(texts).strip() or "Давай продолжим урок."
        self._history.append(DialogMessage(role="assistant", text=reply_text))

        tokens = data.get("usage", {}).get("output_tokens", 0)
        logger.info("[Claude] Ответ (%d токенов): %s", tokens, reply_text[:80])

        return DialogResponse(text=reply_text, used_chunks=chunks, tokens_used=tokens)

    async def close(self) -> None:
        await self._client.aclose()

    def get_history(self) -> list[DialogMessage]:
        return list(self._history)


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
    max_turns: int = 10,
    rag_block: str = "",
) -> list[dict]:
    """Build messages list for Claude API from dialog history."""
    recent = history[-(max_turns * 2):]

    messages = []
    for i, msg in enumerate(recent):
        is_last = i == len(recent) - 1

        if msg.role == "user" and is_last and rag_block:
            content = f"{msg.text}\n\n[Контекст]\n{rag_block}"
        else:
            content = msg.text

        messages.append({"role": msg.role, "content": content})

    return messages


def _extract_reply(data: dict) -> str:
    """Extract text from Claude API response."""
    try:
        blocks = data.get("content", [])
        texts = [b["text"] for b in blocks if b.get("type") == "text"]
        return " ".join(texts).strip() or "Не могу ответить."
    except Exception:
        return "Давай продолжим урок."


# ──────────────────────────────────────────────────────────────────────────
# Фабрика — выбор движка
# ──────────────────────────────────────────────────────────────────────────

def make_dialog_engine(
    retriever: RAGRetriever,
    topic_context: str,
) -> BaseDialogEngine:
    """
    Выбор движка по приоритету (цена/качество):
      1. LLM_STUB_MODE=true → StubDialogEngine
      2. GEMINI_API_KEY → GeminiFlashEngine ($0.01/урок)
      3. DEEPSEEK_API_KEY → DeepSeekEngine ($0.02/урок)
      4. ANTHROPIC_API_KEY → ClaudeDialogEngine ($0.10/урок)
      5. нет ключей → TemplateDialogEngine ($0)
    """
    if os.getenv("LLM_STUB_MODE", "false").lower() == "true":
        logger.info("[LLM] stub-режим")
        return StubDialogEngine()

    # Приоритет: Gemini → DeepSeek → Claude → Template
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        logger.info("[LLM] Gemini Flash (модель=%s, $0.01/урок)", GEMINI_MODEL)
        return GeminiFlashEngine(
            api_key=gemini_key,
            retriever=retriever,
            topic_context=topic_context,
        )

    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        logger.info("[LLM] DeepSeek (модель=%s, $0.02/урок)", DEEPSEEK_MODEL)
        return DeepSeekEngine(
            api_key=deepseek_key,
            retriever=retriever,
            topic_context=topic_context,
        )

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        logger.info("[LLM] Claude Haiku (модель=%s, $0.10/урок)", CLAUDE_MODEL)
        return ClaudeDialogEngine(
            api_key=anthropic_key,
            retriever=retriever,
            topic_context=topic_context,
        )

    logger.info("[LLM] Template engine ($0/урок) — нет API ключей")
    return TemplateDialogEngine(retriever=retriever)
