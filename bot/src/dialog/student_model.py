"""
Student Model — модель ученика для отслеживания прогресса и понимания.

Отслеживает:
  1. Уровень понимания по каждому шагу урока
  2. Паттерны ошибок (где ученик чаще всего путается)
  3. Сильные стороны (что даётся легко)
  4. Темп обучения (быстро/медленно усваивает)
  5. Стиль обучения (через вопросы / через примеры / через практику)
  6. Эмоциональное состояние (уверенность / тревога / скука)

Модель обновляется после каждого взаимодействия и используется для:
  - Выбора стратегии обучения
  - Адаптации сложности
  - Формирования рекомендаций для следующего урока
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from src.dialog.teaching_strategies import UnderstandingLevel

logger = logging.getLogger(__name__)


class EmotionState(Enum):
    """Эмоциональное состояние ученика."""
    ENGAGED = "engaged"           # вовлечён, интересуется
    CONFIDENT = "confident"       # уверен в себе
    UNCERTAIN = "uncertain"       # не уверен, сомневается
    CONFUSED = "confused"         # запутался, не понимает
    FRUSTRATED = "frustrated"     # раздражён, теряет интерес
    BORED = "bored"               # скучает, ему легко
    ANXIOUS = "anxious"           # тревожится, боится ошибиться


class LearningStyle(Enum):
    """Стиль обучения (предпочтения ученика)."""
    VISUAL = "visual"             # лучше усваивает через картинки/схемы
    AUDITORY = "auditory"         # лучше через объяснения
    KINESTHETIC = "kinesthetic"   # лучше через практику/задачи
    READING = "reading"           # лучше через текст/конспекты
    MIXED = "mixed"               # смешанный стиль


@dataclass
class StepPerformance:
    """Производительность ученика на конкретном шаге."""
    step_index: int
    understanding: UnderstandingLevel
    emotion: EmotionState
    attempts: int = 1             # сколько попыток потребовалось
    time_spent_sec: float = 0.0   # сколько времени потрачено
    errors: list[str] = field(default_factory=list)  # типы ошибок
    questions_asked: int = 0      # сколько вопросов задал
    correct_answers: int = 0
    incorrect_answers: int = 0


@dataclass
class StudentModel:
    """Полная модель ученика для текущего урока."""

    # Общие характеристики
    student_name: str = "ученик"
    grade: int = 9                # класс
    learning_style: LearningStyle = LearningStyle.MIXED

    # Текущее состояние
    current_understanding: UnderstandingLevel = UnderstandingLevel.BASIC
    current_emotion: EmotionState = EmotionState.ENGAGED
    overall_confidence: float = 0.5  # 0.0 - 1.0

    # Прогресс по шагам
    step_performances: list[StepPerformance] = field(default_factory=list)

    # Паттерны
    common_errors: list[str] = field(default_factory=list)  # типичные ошибки
    strong_topics: list[str] = field(default_factory=list)  # что даётся легко
    weak_topics: list[str] = field(default_factory=list)    # что сложно

    # Статистика
    total_correct: int = 0
    total_incorrect: int = 0
    total_questions: int = 0
    total_clarifications: int = 0  # сколько раз просил повторить

    # Временные метки
    lesson_start: Optional[datetime] = None
    last_interaction: Optional[datetime] = None

    # Рекомендации для следующего урока
    recommendations: list[str] = field(default_factory=list)

    def update_from_interaction(
        self,
        step_index: int,
        understanding: UnderstandingLevel,
        emotion: EmotionState,
        is_correct: Optional[bool] = None,
        questions_asked: int = 0,
        time_spent: float = 0.0,
        errors: list[str] | None = None,
    ) -> None:
        """
        Обновить модель ученика после взаимодействия.
        """
        self.last_interaction = datetime.now(timezone.utc)

        # Обновляем или создаём запись для шага
        existing = next(
            (p for p in self.step_performances if p.step_index == step_index),
            None,
        )

        if existing:
            existing.attempts += 1
            existing.understanding = understanding
            existing.emotion = emotion
            existing.questions_asked += questions_asked
            existing.time_spent_sec += time_spent
            if errors:
                existing.errors.extend(errors)
            if is_correct is True:
                existing.correct_answers += 1
            elif is_correct is False:
                existing.incorrect_answers += 1
        else:
            perf = StepPerformance(
                step_index=step_index,
                understanding=understanding,
                emotion=emotion,
                time_spent_sec=time_spent,
                errors=errors or [],
                questions_asked=questions_asked,
                correct_answers=1 if is_correct is True else 0,
                incorrect_answers=1 if is_correct is False else 0,
            )
            self.step_performances.append(perf)

        # Обновляем общую статистику
        if is_correct is True:
            self.total_correct += 1
        elif is_correct is False:
            self.total_incorrect += 1
        self.total_questions += questions_asked

        # Обновляем текущее состояние
        self.current_understanding = understanding
        self.current_emotion = emotion

        # Обновляем уверенность
        self._update_confidence(is_correct, understanding)

        # Обновляем паттерны
        self._update_patterns(step_index, understanding, errors)

        logger.debug(
            "[StudentModel] Обновление: step=%d understanding=%s emotion=%s confidence=%.2f",
            step_index, understanding.value, emotion.value, self.overall_confidence,
        )

    def _update_confidence(
        self,
        is_correct: Optional[bool],
        understanding: UnderstandingLevel,
    ) -> None:
        """Обновить уровень уверенности ученика."""
        if is_correct is True:
            self.overall_confidence = min(1.0, self.overall_confidence + 0.1)
        elif is_correct is False:
            self.overall_confidence = max(0.0, self.overall_confidence - 0.15)

        # Корректируем на основе понимания
        understanding_bonus = {
            UnderstandingLevel.CONFUSED: -0.1,
            UnderstandingLevel.UNCERTAIN: -0.05,
            UnderstandingLevel.BASIC: 0.0,
            UnderstandingLevel.PROFICIENT: 0.05,
            UnderstandingLevel.ADVANCED: 0.1,
        }
        self.overall_confidence = max(0.0, min(1.0,
            self.overall_confidence + understanding_bonus.get(understanding, 0.0)
        ))

    def _update_patterns(
        self,
        step_index: int,
        understanding: UnderstandingLevel,
        errors: list[str] | None,
    ) -> None:
        """Обновить паттерны ошибок и сильных сторон."""
        if understanding in (UnderstandingLevel.CONFUSED, UnderstandingLevel.UNCERTAIN):
            # Запоминаем слабые темы
            topic_key = f"step_{step_index}"
            if topic_key not in self.weak_topics:
                self.weak_topics.append(topic_key)

        if understanding in (UnderstandingLevel.PROFICIENT, UnderstandingLevel.ADVANCED):
            # Запоминаем сильные темы
            topic_key = f"step_{step_index}"
            if topic_key not in self.strong_topics:
                self.strong_topics.append(topic_key)

        # Запоминаем типы ошибок
        if errors:
            for error in errors:
                if error not in self.common_errors:
                    self.common_errors.append(error)

    def get_teaching_recommendations(self) -> list[str]:
        """
        Сформировать рекомендации для обучения на основе модели.
        """
        recommendations = []

        # На основе понимания
        confused_steps = [
            p for p in self.step_performances
            if p.understanding == UnderstandingLevel.CONFUSED
        ]
        if confused_steps:
            recommendations.append(
                f"Вернуться к шагам {[p.step_index for p in confused_steps]} — "
                "ученик не понял, нужна дополнительная проработка"
            )

        # На основе ошибок
        if self.common_errors:
            recommendations.append(
                f"Обратить внимание на типичные ошибки: {', '.join(self.common_errors[:3])}"
            )

        # На основе эмоций
        frustrated = [
            p for p in self.step_performances
            if p.emotion in (EmotionState.FRUSTRATED, EmotionState.ANXIOUS)
        ]
        if frustrated:
            recommendations.append(
                "На следующем уроке начать с повторения простых тем для поднятия уверенности"
            )

        bored = [
            p for p in self.step_performances
            if p.emotion == EmotionState.BORED
        ]
        if bored:
            recommendations.append(
                "Ученику легко — можно увеличить сложность или дать дополнительные задачи"
            )

        # На основе темпа
        if self.total_incorrect > self.total_correct:
            recommendations.append(
                "Много ошибок — возможно стоит вернуться к предыдущей теме"
            )

        # На основе стиля обучения
        if self.total_clarifications > 3:
            recommendations.append(
                "Ученик часто просит повторить — попробовать другой способ объяснения"
            )

        return recommendations

    def get_summary(self) -> str:
        """Получить краткую сводку о ученике."""
        accuracy = (
            self.total_correct / max(1, self.total_correct + self.total_incorrect)
            * 100
        )

        parts = [
            f"Ученик: {self.student_name} ({self.grade} класс)",
            f"Уровень понимания: {self.current_understanding.value}",
            f"Эмоциональное состояние: {self.current_emotion.value}",
            f"Уверенность: {self.overall_confidence:.0%}",
            f"Точность ответов: {accuracy:.0f}% ({self.total_correct}/{self.total_correct + self.total_incorrect})",
            f"Вопросов задано: {self.total_questions}",
            f"Просил повторить: {self.total_clarifications} раз",
        ]

        if self.weak_topics:
            parts.append(f"Слабые темы: {', '.join(self.weak_topics[:5])}")
        if self.strong_topics:
            parts.append(f"Сильные темы: {', '.join(self.strong_topics[:5])}")

        return "\n".join(parts)

    def to_dict(self) -> dict:
        """Сериализовать модель в словарь для сохранения."""
        return {
            "student_name": self.student_name,
            "grade": self.grade,
            "learning_style": self.learning_style.value,
            "current_understanding": self.current_understanding.value,
            "current_emotion": self.current_emotion.value,
            "overall_confidence": self.overall_confidence,
            "total_correct": self.total_correct,
            "total_incorrect": self.total_incorrect,
            "total_questions": self.total_questions,
            "total_clarifications": self.total_clarifications,
            "common_errors": self.common_errors,
            "strong_topics": self.strong_topics,
            "weak_topics": self.weak_topics,
            "recommendations": self.recommendations,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StudentModel":
        """Десериализовать модель из словаря."""
        return cls(
            student_name=data.get("student_name", "ученик"),
            grade=data.get("grade", 9),
            learning_style=LearningStyle(data.get("learning_style", "mixed")),
            current_understanding=UnderstandingLevel(data.get("current_understanding", "basic")),
            current_emotion=EmotionState(data.get("current_emotion", "engaged")),
            overall_confidence=data.get("overall_confidence", 0.5),
            total_correct=data.get("total_correct", 0),
            total_incorrect=data.get("total_incorrect", 0),
            total_questions=data.get("total_questions", 0),
            total_clarifications=data.get("total_clarifications", 0),
            common_errors=data.get("common_errors", []),
            strong_topics=data.get("strong_topics", []),
            weak_topics=data.get("weak_topics", []),
            recommendations=data.get("recommendations", []),
        )
