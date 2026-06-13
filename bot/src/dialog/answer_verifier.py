"""
Answer Verifier — проверка фактической правильности ответов ученика через LLM.

Зачем:
  IntentClassifier проверяет ответы только по паттернам (длина строки, ключевые слова).
  Это приводит к тому, что абсурдные ответы считаются правильными.
  AnswerVerifier вызывает Claude API для проверки фактической корректности.

Как работает:
  1. Получает вопрос + ответ ученика
  2. Отправляет в Claude API с инструкцией проверить
  3. Возвращает: is_correct, confidence, explanation
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-haiku-4-5-20251001"
API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
VERIFY_TIMEOUT = 10.0  # быстрая проверка — не блокируем урок


VERIFY_PROMPT = """\
Ты — преподаватель химии. Проверь ответ ученика на вопрос.

Вопрос: {question}
Ответ ученика: {student_answer}
{correct_answer_line}
{topic_context_line}

Определи:
1. Правильный ли ответ (true / false / partially)
2. Насколько ты уверен (0.0 - 1.0)
3. Если неправильно — объясни почему (1-2 предложения, простым языком)
4. Если частично — что правильно, а что нет

Ответь ТОЛЬКО валидным JSON (без markdown):
{{"is_correct": true/false, "confidence": 0.9, "explanation": "..."}}
"""


@dataclass
class AnswerVerification:
    """Результат проверки ответа."""
    is_correct: bool
    confidence: float
    explanation: str


class AnswerVerifier:
    """
    Проверяет фактическую правильность ответов ученика через Claude API.
    """

    def __init__(self, api_key: str):
        self._client = httpx.AsyncClient(
            headers={
                "x-api-key": api_key,
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
            },
            timeout=VERIFY_TIMEOUT,
        )

    async def verify(
        self,
        question: str,
        student_answer: str,
        correct_answer_hint: str = "",
        topic_context: str = "",
    ) -> Optional[AnswerVerification]:
        """
        Проверить ответ ученика через LLM.

        Args:
            question: вопрос преподавателя
            student_answer: ответ ученика (распознанная речь)
            correct_answer_hint: правильный ответ из скрипта (если есть)
            topic_context: контекст темы урока

        Returns:
            AnswerVerification или None при ошибке
        """
        if not question.strip() or not student_answer.strip():
            return None

        correct_line = f"Ожидаемый ответ: {correct_answer_hint}" if correct_answer_hint else ""
        topic_line = f"Тема урока: {topic_context}" if topic_context else ""

        prompt = VERIFY_PROMPT.format(
            question=question,
            student_answer=student_answer,
            correct_answer_line=correct_line,
            topic_context_line=topic_line,
        )

        try:
            resp = await self._client.post(
                API_URL,
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 200,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()

            reply_text = self._extract_text(data)
            return self._parse_verification(reply_text)

        except httpx.HTTPStatusError as e:
            logger.warning("[AnswerVerifier] HTTP %s: %s", e.response.status_code, e.response.text[:200])
            return None
        except Exception as e:
            logger.warning("[AnswerVerifier] Ошибка: %s", e)
            return None

    def _extract_text(self, data: dict) -> str:
        blocks = data.get("content", [])
        texts = [b["text"] for b in blocks if b.get("type") == "text"]
        return " ".join(texts).strip()

    def _parse_verification(self, text: str) -> Optional[AnswerVerification]:
        """Парсим JSON-ответ от LLM."""
        # Убираем markdown-обёртку если есть
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
        text = text.strip()

        try:
            data = json.loads(text)
            return AnswerVerification(
                is_correct=bool(data.get("is_correct", False)),
                confidence=float(data.get("confidence", 0.5)),
                explanation=str(data.get("explanation", "")),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("[AnswerVerifier] Не удалось распарсить ответ: %s | текст: %s", e, text[:200])
            return None

    async def close(self) -> None:
        await self._client.aclose()


class StubAnswerVerifier:
    """Заглушка для тестов и LLM_STUB_MODE."""

    async def verify(self, **kwargs) -> Optional[AnswerVerification]:
        return None

    async def close(self) -> None:
        pass


def make_answer_verifier() -> "AnswerVerifier | StubAnswerVerifier":
    """Фабрика: реальный верификатор или заглушка."""
    if os.getenv("LLM_STUB_MODE", "false").lower() == "true":
        return StubAnswerVerifier()

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return StubAnswerVerifier()

    return AnswerVerifier(api_key=api_key)
