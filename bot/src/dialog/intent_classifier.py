"""
Intent Classifier — классификация намерений ученика.

Определяет тип вопроса/реплики ученика для выбораropriate teaching strategy:
  - on_topic_question: вопрос по текущей теме урока
  - off_topic_question: вопрос не по теме
  - clarification_request: просьба повторить/уточнить
  - confusion_signal: ученик не понял объяснение
  - correct_answer: ученик дал правильный ответ
  - incorrect_answer: ученик ошибся
  - engagement_check: ученик проверяет, слушает ли бот
  - filler: заполнитель паузы (мм, ээ)
  - off_topic_chat: разговор не по делу
  - greeting: приветствие
  - farewell: прощание

Классификация происходит на основе:
  1. Ключевых фраз и паттернов (быстро, без LLM)
  2. Контекста текущего шага урока
  3. Истории последних реплик
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class IntentType(Enum):
    ON_TOPIC_QUESTION = "on_topic_question"
    OFF_TOPIC_QUESTION = "off_topic_question"
    CLARIFICATION_REQUEST = "clarification_request"
    CONFUSION_SIGNAL = "confusion_signal"
    CORRECT_ANSWER = "correct_answer"
    INCORRECT_ANSWER = "incorrect_answer"
    ENGAGEMENT_CHECK = "engagement_check"
    FILLER = "filler"
    OFF_TOPIC_CHAT = "off_topic_chat"
    GREETING = "greeting"
    FAREWELL = "farewell"
    SILENCE = "silence"


@dataclass
class ClassifiedIntent:
    type: IntentType
    confidence: float  # 0.0 - 1.0
    keywords_found: list[str]
    is_question: bool = False
    needs_detail: bool = True


# ──────────────────────────────────────────────────────────────────────────
# Паттерны для классификации (русский язык)
# ──────────────────────────────────────────────────────────────────────────

# Вопросительные конструкции
QUESTION_PATTERNS = [
    r"(?:что|как|почему|зачем|когда|где|сколько|какой|какая|какие|каков|кто|чь[яеи])\s",
    r"(?:объясни|расскажи|покажи|поясни|разъясни)",
    r"(?:можно ли|возможно ли|существует ли|бывает ли)",
    r"\?$",
]

# Сигналы непонимания
CONFUSION_PATTERNS = [
    r"(?:не понял|не поняла|не понимаю|непонятно|сложно|трудно)",
    r"(?:что(?:-то|то) не так|что-то не то|не то|не так)",
    r"(?:можешь повторить|повтори|ещё раз|заново|по-другому)",
    r"(?:а (?:что|как|почему|зачем)(?:\s+(?:это|так|же))?$)",  # "а что", "а как" — но не "а что такое X?"
    r"(?:я запутался|запуталась|перепутал|перепутала)",
    r"(?:непонятно|нечего)",
]

# Правильные ответы
CORRECT_ANSWER_PATTERNS = [
    r"^(?:да|нет|верно|правильно|именно|точно|менно|в precisely)$",
    r"(?:это (?:правильно|верно|точно|именно))",
    r"(?:я (?:понял|поняла|запомнил|запомнила))",
    r"(?:понятно|ясно|понял|поняла)",
    r"^(?:ага|угу|точно|именно)$",
]

# Неправильные ответы (типичные ошибки)
INCORRECT_ANSWER_PATTERNS = [
    r"(?:а (?:не|вроде не|не совсем|не exactly))",
    r"(?:не уверен|не уверена|кажется|может быть|наверное)",
    r"(?:я думал|думала|мне казалось)",
    r"^(?:нет|не)$",
]

# Проверка на вовлечённость
ENGAGEMENT_PATTERNS = [
    r"(?:ты там|ты слышишь|ты меня слышишь|ты есть|ты онлайн)",
    r"(?:давай|ну|продолжай|поехали|вперёд)",
    r"(?:да-да|ага|угу|мм|хм)",
]

# Заполнители паузы
FILLER_PATTERNS = [
    r"^(?:мм|ммм|ээ|эээ|ну|так|значит|короче)$",
    r"^(?:а|э|о|у|и|ы)$",
]

# Приветствия
GREETING_PATTERNS = [
    r"(?:привет|здравствуй|здравствуйте|добрый|добрый день|добрый вечер|хай|хей|йо)",
    r"(?:доброе утро|добрый день|добрый вечер)",
]

# Прощания
FAREWELL_PATTERNS = [
    r"(?:пока|до свидания|до встречи|прощай|увидимся)",
    r"(?:мне пора|надо идти|я пошёл|я пошла|я ухожу)",
]

# Смежные темы химии (не текущая тема, но related)
CHEMISTRY_KEYWORDS = [
    "реакция", "молекула", "атом", "элемент", "период", "группа",
    "валентность", "окисление", "восстановление", " электрон",
    "ион", "связь", "органика", "неорганика", "кислота", "основание",
    "соль", "щёлочь", "раствор", "концентрация", "стехиометрия",
]


# ──────────────────────────────────────────────────────────────────────────
# Классификатор
# ──────────────────────────────────────────────────────────────────────────

class IntentClassifier:
    """
    Классифицирует реплику ученика по намерению.
    Использует паттерны + контекст урока для быстрой классификации.
    """

    def __init__(self, current_topic_keywords: str = ""):
        self._topic_keywords = current_topic_keywords.lower()

    def classify(
        self,
        text: str,
        last_bot_message: str = "",
        current_step_question: str = "",
    ) -> ClassifiedIntent:
        """
        Классифицировать реплику ученика.

        Args:
            text: распознанная речь ученика
            last_bot_message: последнее сообщение бота (контекст)
            current_step_question: вопрос текущего шага сценария
        """
        if not text or not text.strip():
            return ClassifiedIntent(
                type=IntentType.SILENCE,
                confidence=1.0,
                keywords_found=[],
            )

        text_lower = text.lower().strip()
        words_found = []

        # 1. Проверяем заполнители (самые простые паттерны)
        for pattern in FILLER_PATTERNS:
            if re.search(pattern, text_lower):
                return ClassifiedIntent(
                    type=IntentType.FILLER,
                    confidence=0.9,
                    keywords_found=[text_lower],
                )

        # 2. Приветствия
        for pattern in GREETING_PATTERNS:
            if re.search(pattern, text_lower):
                return ClassifiedIntent(
                    type=IntentType.GREETING,
                    confidence=0.95,
                    keywords_found=[text_lower],
                )

        # 3. Прощания
        for pattern in FAREWELL_PATTERNS:
            if re.search(pattern, text_lower):
                return ClassifiedIntent(
                    type=IntentType.FAREWELL,
                    confidence=0.9,
                    keywords_found=[text_lower],
                )

        # 4. Проверка на вовлечённость
        for pattern in ENGAGEMENT_PATTERNS:
            if re.search(pattern, text_lower):
                return ClassifiedIntent(
                    type=IntentType.ENGAGEMENT_CHECK,
                    confidence=0.85,
                    keywords_found=[text_lower],
                )

        # 5. Сигналы непонимания
        for pattern in CONFUSION_PATTERNS:
            if re.search(pattern, text_lower):
                return ClassifiedIntent(
                    type=IntentType.CONFUSION_SIGNAL,
                    confidence=0.8,
                    keywords_found=[text_lower],
                )

        # 6. Определяем, является ли это ответом на вопрос
        is_answer_context = bool(current_step_question)

        if is_answer_context:
            # Проверяем правильность ответа
            is_correct = self._check_answer_correctness(
                text_lower, current_step_question, last_bot_message
            )
            if is_correct is True:
                return ClassifiedIntent(
                    type=IntentType.CORRECT_ANSWER,
                    confidence=0.75,
                    keywords_found=[text_lower],
                )
            elif is_correct is False:
                return ClassifiedIntent(
                    type=IntentType.INCORRECT_ANSWER,
                    confidence=0.7,
                    keywords_found=[text_lower],
                )

        # 7. Определяем, вопрос ли это
        is_question = False
        for pattern in QUESTION_PATTERNS:
            if re.search(pattern, text_lower):
                is_question = True
                break

        # 8. Проверяем, по теме ли вопрос
        if is_question:
            on_topic = self._is_on_topic(text_lower)
            if on_topic:
                return ClassifiedIntent(
                    type=IntentType.ON_TOPIC_QUESTION,
                    confidence=0.7,
                    keywords_found=words_found,
                    is_question=True,
                )
            else:
                return ClassifiedIntent(
                    type=IntentType.OFF_TOPIC_QUESTION,
                    confidence=0.6,
                    keywords_found=words_found,
                    is_question=True,
                )

        # 9. По умолчанию — разговор не по делу
        return ClassifiedIntent(
            type=IntentType.OFF_TOPIC_CHAT,
            confidence=0.5,
            keywords_found=words_found,
        )

    def _check_answer_correctness(
        self,
        answer: str,
        question: str,
        context: str,
    ) -> Optional[bool]:
        """
        Проверить правильность ответа ученика.
        Возвращает True (правильно), False (неправильно) или None (не удалось определить).
        """
        # Простые проверки на основе вопроса
        question_lower = question.lower()

        # Вопросы типа "что такое X?" — ученик должен дать определение
        if "что такое" in question_lower or "что означает" in question_lower:
            if len(answer.split()) >= 2:  # минимум 2 слова для определения
                return True  # считаем правильным если ответ развёрнутый

        # Вопросы типа "сколько?" — ученик должен назвать число
        if "сколько" in question_lower or "какое число" in question_lower:
            if re.search(r"\d+", answer):
                return True

        # Вопросы типа "верно ли?" — проверяем на да/нет
        if "верно ли" in question_lower or "правильно ли" in question_lower:
            if answer in ("да", "нет", "верно", "неверно", "правильно", "неправильно"):
                return True

        # Вопросы типа "Это X?" — проверяем на да/нет
        if question_lower.startswith("это ") or question_lower.endswith("?"):
            if answer in ("да", "нет", "ага", "угу", "точно", "именно"):
                return True
            elif answer in ("не", "неа", "не совсем", "вроде нет"):
                return False

        # Не можем определить — нужен LLM для проверки
        return None

    def _is_on_topic(self, text: str) -> bool:
        """Проверить, связана ли реплика с текущей темой урока."""
        if not self._topic_keywords:
            return True  # если ключевые слова не заданы, считаем что по теме

        # Разбиваем ключевые слова темы
        topic_words = set(self._topic_keywords.split())

        # Разбиваем текст и убираем знаки препинания
        text_words = set(w.strip("?!.,;:") for w in text.split())

        # Есть пересечение — по теме
        overlap = topic_words & text_words
        if overlap:
            return True

        # Проверяем химические термины
        for kw in CHEMISTRY_KEYWORDS:
            if kw in text:
                return True

        return False


# ──────────────────────────────────────────────────────────────────────────
# Утилиты
# ──────────────────────────────────────────────────────────────────────────

def get_intent_description(intent: IntentType) -> str:
    """Получить описание намерения на русском."""
    descriptions = {
        IntentType.ON_TOPIC_QUESTION: "Вопрос по текущей теме",
        IntentType.OFF_TOPIC_QUESTION: "Вопрос не по теме",
        IntentType.CLARIFICATION_REQUEST: "Просьба уточнить/повторить",
        IntentType.CONFUSION_SIGNAL: "Сигнал непонимания",
        IntentType.CORRECT_ANSWER: "Правильный ответ",
        IntentType.INCORRECT_ANSWER: "Неправильный ответ",
        IntentType.ENGAGEMENT_CHECK: "Проверка вовлечённости",
        IntentType.FILLER: "Заполнитель паузы",
        IntentType.OFF_TOPIC_CHAT: "Разговор не по делу",
        IntentType.GREETING: "Приветствие",
        IntentType.FAREWELL: "Прощание",
        IntentType.SILENCE: "Тишина",
    }
    return descriptions.get(intent, "Неизвестное намерение")
