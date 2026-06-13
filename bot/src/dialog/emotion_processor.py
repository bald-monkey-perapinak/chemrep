# -*- coding: utf-8 -*-
"""
Emotion-Aware Post-Processor — постобработка ответов с учётом эмоций.

Дорабатывает ответ LLM для более естественного звучания:
  1. Добавляет паузы (многоточия) для естественных остановок
  2. Корректирует эмоциональную окраску в зависимости от ситуации
  3. Добавляет слова-поддержки при непонимании
  4. Убирает формальные конструкции
  5. Добавляет живые элементы (восклицания, уточнения)
  6. Форматирует для TTS (знаки препинания для интонации)

Цель — сделать ответ максимально похожим на живого человека.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from src.dialog.teaching_strategies import UnderstandingLevel, TeachingMethod
from src.dialog.student_model import EmotionState
from src.dialog.intent_classifier import IntentType

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# Паттерны для постобработки
# ──────────────────────────────────────────────────────────────────────────

# Формальные конструкции, которые нужно убирать или заменять
FORMAL_PATTERNS = [
    (r"Следует отметить, что", ""),
    (r"Необходимо обратить внимание на то, что", "Важно:"),
    (r"В соответствии с", "По"),
    (r"На основании вышеизложенного", "Итак"),
    (r"Таким образом", "Значит"),
    (r"В заключение необходимо отметить", "Кстати"),
    (r"Данный", "Этот"),
    (r"Осуществляется", "Происходит"),
    (r"Представляет собой", "Это"),
]

# Эмоциональные маркеры для разных ситуаций
EMOTION_MARKERS = {
    EmotionState.CONFUSED: [
        "Не переживай,",
        "Ничего страшного,",
        "Это нормально,",
        "Давай разберёмся,",
    ],
    EmotionState.FRUSTRATED: [
        "Я понимаю,",
        "Это действительно сложно,",
        "Давай не торопиться,",
        "Мы справимся,",
    ],
    EmotionState.ANXIOUS: [
        "Всё хорошо,",
        "Не волнуйся,",
        "Ты справляешься,",
        "Мы慢慢来,",
    ],
    EmotionState.BORED: [
        "А теперь интересное,",
        "Знаешь что интересно?",
        "А ты знал, что",
        "Давай кое-что крутое",
    ],
}

# Маркеры поддержки при правильных ответах
CORRECT_MARKERS = [
    "Отлично!",
    "Молодец!",
    "Именно так!",
    "Ты точно понял!",
    "Вот это я понимаю!",
    "Правильно!",
    "Умница!",
]

# Маркеры при неправильных ответах
INCORRECT_MARKERS = [
    "Почти!",
    "Ты близко!",
    "Давай уточним!",
    "Не совсем, но ты на правильном пути!",
    "Хорошая попытка!",
]


# ──────────────────────────────────────────────────────────────────────────
# Постпроцессор
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class PostProcessConfig:
    """Конфигурация постобработки."""
    add_pauses: bool = True           # добавлять паузы (многоточия)
    remove_formal: bool = True        # убирать формальные конструкции
    add_emotion_markers: bool = True  # добавлять эмоциональные маркеры
    add_support_markers: bool = True  # добавлять слова поддержки
    max_length: int = 500             # максимальная длина ответа (символов)
    tts_friendly: bool = True         # форматировать для TTS


class EmotionAwarePostProcessor:
    """
    Постобработка ответов LLM с учётом эмоционального состояния.
    """

    def __init__(self, config: Optional[PostProcessConfig] = None):
        self._config = config or PostProcessConfig()

    def process(
        self,
        text: str,
        intent: Optional[IntentType] = None,
        emotion: Optional[EmotionState] = None,
        understanding: Optional[UnderstandingLevel] = None,
        strategy: Optional[TeachingMethod] = None,
    ) -> str:
        """
        Постобработать ответ LLM.

        Args:
            text: исходный ответ LLM
            intent: тип намерения ученика
            emotion: эмоциональное состояние ученика
            understanding: уровень понимания
            strategy: выбранная стратегия обучения
        """
        if not text or not text.strip():
            return text

        result = text

        # 1. Убираем формальные конструкции
        if self._config.remove_formal:
            result = self._remove_formal(result)

        # 2. Добавляем эмоциональные маркеры
        if self._config.add_emotion_markers and emotion:
            result = self._add_emotion_markers(result, emotion, intent)

        # 3. Добавляем слова поддержки
        if self._config.add_support_markers:
            result = self._add_support_markers(result, intent, understanding)

        # 4. Добавляем паузы для естественности
        if self._config.add_pauses:
            result = self._add_pauses(result)

        # 5. Форматируем для TTS
        if self._config.tts_friendly:
            result = self._format_for_tts(result)

        # 6. Ограничиваем длину
        if len(result) > self._config.max_length:
            result = self._truncate_naturally(result, self._config.max_length)

        return result

    def _remove_formal(self, text: str) -> str:
        """Убрать формальные конструкции."""
        result = text
        for pattern, replacement in FORMAL_PATTERNS:
            result = re.sub(pattern, replacement, result)
        return result

    def _add_emotion_markers(
        self,
        text: str,
        emotion: EmotionState,
        intent: Optional[IntentType] = None,
    ) -> str:
        """Добавить эмоциональные маркеры в начало ответа."""
        markers = EMOTION_MARKERS.get(emotion, [])

        if not markers:
            return text

        # Не добавляем маркеры если ответ уже начинается с эмоционального слова
        first_word = text.split()[0] if text.split() else ""
        emotional_starts = [
            "отлично", "молодец", "хорошо", "прекрасно", "замечательно",
            "не переживай", "ничего", "давай", "понимаю",
        ]
        if first_word.lower() in emotional_starts:
            return text

        # Выбираем подходящий маркер
        import random
        marker = random.choice(markers)

        # Добавляем в начало
        if text[0].isupper():
            return f"{marker} {text}"
        else:
            return f"{marker} {text[0].lower()}{text[1:]}"

    def _add_support_markers(
        self,
        text: str,
        intent: Optional[IntentType] = None,
        understanding: Optional[UnderstandingLevel] = None,
    ) -> str:
        """Добавить слова поддержки при необходимости."""
        if not intent:
            return text

        # При правильном ответе — похвала
        if intent == IntentType.CORRECT_ANSWER:
            import random
            marker = random.choice(CORRECT_MARKERS)
            # Добавляем в начало если ещё нет похвалы
            if not any(m.lower() in text.lower() for m in CORRECT_MARKERS):
                return f"{marker} {text}"

        # При неправильном ответе — поддержка
        if intent == IntentType.INCORRECT_ANSWER:
            import random
            marker = random.choice(INCORRECT_MARKERS)
            if not any(m.lower() in text.lower() for m in INCORRECT_MARKERS):
                return f"{marker} {text}"

        # При непонимании — слова поддержки
        if understanding == UnderstandingLevel.CONFUSED:
            if "не переживай" not in text.lower() and "ничего" not in text.lower():
                return f"Не переживай, это нормально. {text}"

        return text

    def _add_pauses(self, text: str) -> str:
        """Добавить паузы для естественности."""
        # Добавляем паузу после длинных предложений
        sentences = text.split(". ")
        if len(sentences) > 2:
            # Добавляем многоточие после каждого второго предложения
            result = []
            for i, sentence in enumerate(sentences):
                if i > 0 and i % 2 == 0 and len(sentence) > 20:
                    result.append(f"... {sentence}")
                else:
                    result.append(sentence)
            return ". ".join(result)

        # Добавляем паузу перед ключевыми словами
        pause_words = ["важно", "запомни", "обрати внимание", "смотри"]
        for word in pause_words:
            if word in text.lower():
                text = text.replace(word, f"... {word}")

        return text

    def _format_for_tts(self, text: str) -> str:
        """Отформатировать текст для TTS (знаки препинания для интонации)."""
        # Заменяем точки с запятой на точки (TTS лучше воспринимает точки)
        text = text.replace(";", ".")

        # Добавляем запятые для пауз (если их мало)
        if text.count(",") < len(text.split()) / 20:
            # Добавляем запятые перед союзами
            conjunctions = ["и", "а", "но", "или", "что", "как", "где", "когда"]
            for conj in conjunctions:
                text = re.sub(rf"\s+{conj}\s+", f", {conj} ", text)

        # Убираем двойные пробелы
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def _truncate_naturally(self, text: str, max_length: int) -> str:
        """Естественно обрезать текст (не на полуслове)."""
        if len(text) <= max_length:
            return text

        # Обрезаем по последнему предложению или запятой
        truncated = text[:max_length]

        # Ищем последнее предложение
        last_period = truncated.rfind(".")
        last_comma = truncated.rfind(",")
        last_space = truncated.rfind(" ")

        # Выбираем лучшую точку обрезки
        cut_point = max(last_period, last_comma, last_space)

        if cut_point > max_length * 0.6:  # если обрезка не слишком короткая
            return truncated[:cut_point + 1].strip() + "..."
        else:
            return truncated.strip() + "..."


# ──────────────────────────────────────────────────────────────────────────
# Утилиты
# ──────────────────────────────────────────────────────────────────────────

def postprocess_response(
    text: str,
    intent: Optional[IntentType] = None,
    emotion: Optional[EmotionState] = None,
    understanding: Optional[UnderstandingLevel] = None,
    strategy: Optional[TeachingMethod] = None,
) -> str:
    """
    Удобная функция для постобработки ответа.
    """
    processor = EmotionAwarePostProcessor()
    return processor.process(text, intent, emotion, understanding, strategy)


def make_natural_speech(text: str) -> str:
    """
    Сделать текст более естественным для произнесения.
    Минимальная обработка — только форматирование для TTS.
    """
    processor = EmotionAwarePostProcessor(config=PostProcessConfig(
        add_pauses=True,
        remove_formal=True,
        add_emotion_markers=False,
        add_support_markers=False,
        tts_friendly=True,
    ))
    return processor.process(text)
