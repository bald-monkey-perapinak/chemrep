# -*- coding: utf-8 -*-
"""
Lesson Summary Generator — генератор сводки урока.

Создаёт подробную сводку по итогам урока:
  1. Что было разобрано (ключевые темы и концепции)
  2. Как ученик справлялся (уровень понимания, ошибки)
  3. Рекомендации для следующего урока
  4. Домашнее задание (если нужно)
  5. Отчёт для родителей/учителя

Используется:
  - В конце урока для озвучки сводки ученику
  - Для сохранения в БД
  - Для генерации отчёта для родителей
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.dialog.student_model import StudentModel, UnderstandingLevel, EmotionState
from src.dialog.teaching_strategies import TeachingMethod

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# Типы данных
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class LessonSummary:
    """Сводка урока."""
    # Основная информация
    topic_name: str
    student_name: str
    lesson_date: str
    duration_minutes: int

    # Что было разобрано
    topics_covered: list[str] = field(default_factory=list)
    key_concepts: list[str] = field(default_factory=list)
    steps_completed: int = 0
    total_steps: int = 0

    # Производительность ученика
    overall_understanding: str = "basic"
    accuracy_percent: float = 0.0
    total_correct: int = 0
    total_incorrect: int = 0
    questions_asked: int = 0
    clarifications_needed: int = 0

    # Ошибки и слабые места
    common_errors: list[str] = field(default_factory=list)
    weak_topics: list[str] = field(default_factory=list)
    strong_topics: list[str] = field(default_factory=list)

    # Рекомендации
    recommendations: list[str] = field(default_factory=list)
    next_lesson_focus: str = ""

    # Для ученика (озвучка)
    student_summary: str = ""
    # Для родителей/учителя (отчёт)
    parent_report: str = ""
    # Краткая сводка
    brief_summary: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Генератор сводки
# ──────────────────────────────────────────────────────────────────────────

class LessonSummaryGenerator:
    """Генерирует сводку урока на основе модели ученика и хода урока."""

    def __init__(
        self,
        student_model: StudentModel,
        topic_name: str = "",
        lesson_start: Optional[datetime] = None,
    ):
        self._model = student_model
        self._topic_name = topic_name
        self._lesson_start = lesson_start or datetime.now(timezone.utc)

    def generate(
        self,
        topics_covered: list[str] | None = None,
        steps_completed: int = 0,
        total_steps: int = 0,
    ) -> LessonSummary:
        """Сгенерировать полную сводку урока."""
        model = self._model

        # Рассчитываем метрики
        total_answers = model.total_correct + model.total_incorrect
        accuracy = (model.total_correct / max(1, total_answers)) * 100

        # Определяем общий уровень понимания
        understanding = self._determine_overall_understanding()

        # Рассчитываем длительность
        duration = self._calculate_duration()

        # Формируем рекомендации
        recommendations = self._generate_recommendations(understanding, accuracy)

        # Формируем фокус следующего урока
        next_focus = self._determine_next_focus()

        # Генерируем тексты сводок
        student_summary = self._generate_student_summary(
            understanding, accuracy, recommendations
        )
        parent_report = self._generate_parent_report(
            understanding, accuracy, recommendations, next_focus
        )
        brief_summary = self._generate_brief_summary(understanding, accuracy)

        return LessonSummary(
            topic_name=self._topic_name,
            student_name=model.student_name,
            lesson_date=self._lesson_start.strftime("%d.%m.%Y"),
            duration_minutes=duration,
            topics_covered=topics_covered or [],
            key_concepts=self._extract_key_concepts(),
            steps_completed=steps_completed,
            total_steps=total_steps,
            overall_understanding=understanding.value,
            accuracy_percent=accuracy,
            total_correct=model.total_correct,
            total_incorrect=model.total_incorrect,
            questions_asked=model.total_questions,
            clarifications_needed=model.total_clarifications,
            common_errors=model.common_errors,
            weak_topics=model.weak_topics,
            strong_topics=model.strong_topics,
            recommendations=recommendations,
            next_lesson_focus=next_focus,
            student_summary=student_summary,
            parent_report=parent_report,
            brief_summary=brief_summary,
        )

    def _determine_overall_understanding(self) -> UnderstandingLevel:
        """Определить общий уровень понимания."""
        model = self._model

        # Анализируем все шаги
        if not model.step_performances:
            return UnderstandingLevel.BASIC

        confused_count = sum(
            1 for p in model.step_performances
            if p.understanding == UnderstandingLevel.CONFUSED
        )
        proficient_count = sum(
            1 for p in model.step_performances
            if p.understanding in (UnderstandingLevel.PROFICIENT, UnderstandingLevel.ADVANCED)
        )

        total = len(model.step_performances)

        if confused_count > total * 0.5:
            return UnderstandingLevel.CONFUSED
        elif confused_count > total * 0.3:
            return UnderstandingLevel.UNCERTAIN
        elif proficient_count > total * 0.5:
            return UnderstandingLevel.PROFICIENT
        else:
            return UnderstandingLevel.BASIC

    def _calculate_duration(self) -> int:
        """Рассчитать длительность урока в минутах."""
        now = datetime.now(timezone.utc)
        delta = now - self._lesson_start
        return max(1, int(delta.total_seconds() / 60))

    def _extract_key_concepts(self) -> list[str]:
        """Извлечь ключевые концепции из сильных и слабых тем."""
        concepts = []
        concepts.extend(self._model.strong_topics[:3])
        concepts.extend(self._model.weak_topics[:3])
        return list(dict.fromkeys(concepts))  # убираем дубликаты

    def _generate_recommendations(
        self,
        understanding: UnderstandingLevel,
        accuracy: float,
    ) -> list[str]:
        """Сгенерировать рекомендации."""
        recommendations = []
        model = self._model

        # На основе уровня понимания
        if understanding == UnderstandingLevel.CONFUSED:
            recommendations.append(
                "Вернуться к базовым концепциям и объяснить их по-другому"
            )
        elif understanding == UnderstandingLevel.UNCERTAIN:
            recommendations.append(
                "Повторить сложные моменты с новыми примерами"
            )
        elif understanding == UnderstandingLevel.PROFICIENT:
            recommendations.append(
                "Можно переходить к более сложным задачам"
            )

        # На основе точности
        if accuracy < 50:
            recommendations.append(
                "Много ошибок — стоит повторить базовый материал"
            )
        elif accuracy < 70:
            recommendations.append(
                "Есть пробелы — обратить внимание на слабые места"
            )
        elif accuracy > 90:
            recommendations.append(
                "Отличные результаты — можно углубить материал"
            )

        # На основе эмоций
        frustrated_steps = [
            p for p in model.step_performances
            if p.emotion in (EmotionState.FRUSTRATED, EmotionState.ANXIOUS)
        ]
        if frustrated_steps:
            recommendations.append(
                "На следующем уроке начать с простых задач для поднятия уверенности"
            )

        # На основе количества вопросов
        if model.total_clarifications > 3:
            recommendations.append(
                "Ученик часто просит повторить — попробовать другой способ объяснения"
            )

        # На основе слабых тем
        if model.weak_topics:
            recommendations.append(
                f"Обратить внимание на: {', '.join(model.weak_topics[:3])}"
            )

        return recommendations

    def _determine_next_focus(self) -> str:
        """Определить фокус следующего урока."""
        model = self._model

        if model.weak_topics:
            return f"Повторение: {', '.join(model.weak_topics[:2])}"
        elif model.total_incorrect > model.total_correct:
            return "Возврат к базовым концепциям"
        else:
            return "Продолжение темы / углубление"

    def _generate_student_summary(
        self,
        understanding: UnderstandingLevel,
        accuracy: float,
        recommendations: list[str],
    ) -> str:
        """Сгенерировать сводку для ученика (для озвучки)."""
        model = self._model

        parts = []

        # Приветствие и общая оценка
        if accuracy >= 90:
            parts.append(f"Отлично, {model.student_name}! Ты сегодня молодец!")
        elif accuracy >= 70:
            parts.append(f"Хорошая работа, {model.student_name}!")
        elif accuracy >= 50:
            parts.append(f"Неплохо, {model.student_name}! Есть над чем поработать.")
        else:
            parts.append(f"Не переживай, {model.student_name}! Мы разберёмся.")

        # Что разобрали
        parts.append(f"Мы разбирали тему «{self._topic_name}».")

        # Статистика
        parts.append(
            f"Ты ответил правильно на {model.total_correct} из "
            f"{model.total_correct + model.total_incorrect} вопросов."
        )

        # Сильные стороны
        if model.strong_topics:
            parts.append(
                f"Тебе хорошо удалось: {', '.join(model.strong_topics[:2])}."
            )

        # Рекомендации (простым языком)
        if recommendations:
            parts.append(f"На следующем уроке мы обратим внимание на: {recommendations[0]}.")

        return " ".join(parts)

    def _generate_parent_report(
        self,
        understanding: UnderstandingLevel,
        accuracy: float,
        recommendations: list[str],
        next_focus: str,
    ) -> str:
        """Сгенерировать отчёт для родителей/учителя."""
        model = self._model

        lines = [
            f"Отчёт об уроке по химии",
            f"",
            f"Ученик: {model.student_name}",
            f"Дата: {self._lesson_start.strftime('%d.%m.%Y')}",
            f"Тема: {self._topic_name}",
            f"",
            f"Результаты:",
            f"- Уровень понимания: {understanding.value}",
            f"- Точность ответов: {accuracy:.0f}%",
            f"- Правильных ответов: {model.total_correct}",
            f"- Ошибок: {model.total_incorrect}",
            f"- Вопросов задано: {model.total_questions}",
            f"",
        ]

        if model.common_errors:
            lines.append("Типичные ошибки:")
            for error in model.common_errors[:3]:
                lines.append(f"- {error}")
            lines.append("")

        if recommendations:
            lines.append("Рекомендации:")
            for rec in recommendations[:3]:
                lines.append(f"- {rec}")
            lines.append("")

        lines.append(f"Фокус следующего урока: {next_focus}")

        return "\n".join(lines)

    def _generate_brief_summary(
        self,
        understanding: UnderstandingLevel,
        accuracy: float,
    ) -> str:
        """Сгенерировать краткую сводку."""
        model = self._model

        understanding_ru = {
            UnderstandingLevel.CONFUSED: "не понял",
            UnderstandingLevel.UNCERTAIN: "не уверен",
            UnderstandingLevel.BASIC: "базовый",
            UnderstandingLevel.PROFICIENT: "хороший",
            UnderstandingLevel.ADVANCED: "отличный",
        }

        return (
            f"{model.student_name}: {self._topic_name} | "
            f"Понимание: {understanding_ru.get(understanding, 'базовый')} | "
            f"Точность: {accuracy:.0f}%"
        )


# ──────────────────────────────────────────────────────────────────────────
# Утилиты
# ──────────────────────────────────────────────────────────────────────────

def generate_lesson_summary(
    student_model: StudentModel,
    topic_name: str = "",
    topics_covered: list[str] | None = None,
    steps_completed: int = 0,
    total_steps: int = 0,
) -> LessonSummary:
    """
    Удобная функция для генерации сводки урока.
    """
    generator = LessonSummaryGenerator(
        student_model=student_model,
        topic_name=topic_name,
    )
    return generator.generate(
        topics_covered=topics_covered,
        steps_completed=steps_completed,
        total_steps=total_steps,
    )


def format_summary_for_tts(summary: LessonSummary) -> str:
    """Отформатировать сводку для озвучки (TTS)."""
    return summary.student_summary


def format_summary_for_db(summary: LessonSummary) -> dict:
    """Отформатировать сводку для сохранения в БД."""
    return {
        "topic_name": summary.topic_name,
        "student_name": summary.student_name,
        "lesson_date": summary.lesson_date,
        "duration_minutes": summary.duration_minutes,
        "topics_covered": summary.topics_covered,
        "key_concepts": summary.key_concepts,
        "steps_completed": summary.steps_completed,
        "total_steps": summary.total_steps,
        "overall_understanding": summary.overall_understanding,
        "accuracy_percent": summary.accuracy_percent,
        "total_correct": summary.total_correct,
        "total_incorrect": summary.total_incorrect,
        "questions_asked": summary.questions_asked,
        "clarifications_needed": summary.clarifications_needed,
        "common_errors": summary.common_errors,
        "weak_topics": summary.weak_topics,
        "strong_topics": summary.strong_topics,
        "recommendations": summary.recommendations,
        "next_lesson_focus": summary.next_lesson_focus,
        "student_summary": summary.student_summary,
        "parent_report": summary.parent_report,
        "brief_summary": summary.brief_summary,
    }
