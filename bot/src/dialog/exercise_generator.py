"""
Exercise Generator — генерация адаптивных задач на основе ошибок ученика.

Зачем:
  Живой преподаватель после ошибки даёт дополнительную задачу для закрепления.
  ExerciseGenerator генерирует такие задачи через Claude API.

Как работает:
  1. Получает типичные ошибки ученика и его сильные стороны
  2. Генерирует короткую задачу (1-2 вопроса) через LLM
  3. Возвращает текст задачи + правильный ответ + подсказку
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

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
API_URL = os.getenv("ANTHROPIC_API_URL", "https://api.anthropic.com/v1/messages")
API_VERSION = "2023-06-01"
EXERCISE_TIMEOUT = 12.0


EXERCISE_PROMPT = """\
Ты — преподаватель химии. Сгенерируй короткую задачу для закрепления материала.

Тема: {topic_context}
Ошибки ученика: {error_patterns}
Что ученик уже понял: {correct_concepts}
Уровень сложности: {difficulty}

Требования к задаче:
- 1-2 коротких вопроса (не длиннее 3 предложений каждый)
- Соответствует теме урока
- Учитывает типичные ошибки ученика
- После 2+ ошибок подряд — упрощённая задача для поднятия уверенности

Ответь ТОЛЬКО валидным JSON (без markdown):
{{"exercise": "Текст задачи", "answer": "Правильный ответ", "hint": "Подсказка если не справится"}}
"""


@dataclass
class Exercise:
    """Сгенерированная задача."""
    exercise: str
    answer: str
    hint: str


class ExerciseGenerator:
    """
    Генерирует адаптивные задачи через Claude API на основе ошибок ученика.
    """

    def __init__(self, api_key: str):
        self._client = httpx.AsyncClient(
            headers={
                "x-api-key": api_key,
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
            },
            timeout=EXERCISE_TIMEOUT,
        )

    async def generate(
        self,
        topic_context: str,
        error_patterns: list[str],
        correct_concepts: list[str],
        difficulty: str = "easy",
    ) -> Optional[Exercise]:
        """
        Сгенерировать задачу для закрепления.

        Args:
            topic_context: контекст темы урока
            error_patterns: типичные ошибки ученика
            correct_concepts: что ученик уже понял
            difficulty: easy/normal/hard

        Returns:
            Exercise или None при ошибке
        """
        prompt = EXERCISE_PROMPT.format(
            topic_context=topic_context[:500],
            error_patterns=", ".join(error_patterns[:5]) if error_patterns else "нет данных",
            correct_concepts=", ".join(correct_concepts[:5]) if correct_concepts else "нет данных",
            difficulty=difficulty,
        )

        try:
            resp = await self._client.post(
                API_URL,
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()

            reply_text = self._extract_text(data)
            return self._parse_exercise(reply_text)

        except httpx.HTTPStatusError as e:
            logger.warning("[ExerciseGenerator] HTTP %s: %s", e.response.status_code, e.response.text[:200])
            return None
        except Exception as e:
            logger.warning("[ExerciseGenerator] Ошибка: %s", e)
            return None

    def _extract_text(self, data: dict) -> str:
        blocks = data.get("content", [])
        texts = [b["text"] for b in blocks if b.get("type") == "text"]
        return " ".join(texts).strip()

    def _parse_exercise(self, text: str) -> Optional[Exercise]:
        """Парсим JSON-ответ от LLM."""
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
        text = text.strip()

        try:
            data = json.loads(text)
            return Exercise(
                exercise=str(data.get("exercise", "")),
                answer=str(data.get("answer", "")),
                hint=str(data.get("hint", "")),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("[ExerciseGenerator] Не удалось распарсить ответ: %s | текст: %s", e, text[:200])
            return None

    async def close(self) -> None:
        await self._client.aclose()


class StubExerciseGenerator:
    """Заглушка для тестов и LLM_STUB_MODE."""

    async def generate(self, **kwargs) -> Optional[Exercise]:
        return None

    async def close(self) -> None:
        pass


def make_exercise_generator() -> "ExerciseGenerator | StubExerciseGenerator":
    """Фабрика: реальный генератор или заглушка."""
    if os.getenv("LLM_STUB_MODE", "false").lower() == "true":
        return StubExerciseGenerator()

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return StubExerciseGenerator()

    return ExerciseGenerator(api_key=api_key)
