"""
Teaching Strategies — стратегии обучения для профессионального репетитора.

Реализует проверенные методики обучения:
  1. Socratic Method — подводящие вопросы вместо прямых ответов
  2. Scaffolding — пошаговая поддержка с постепенным усложнением
  3. Elaborative Interrogation — "почему?" и "как именно?"
  4. Retrieval Practice — активное вспоминание вместо пассивного повторения
  5. Interleaving — чередование тем для лучшего запоминания
  6. Concrete Examples — абстрактные концепции через конкретные примеры
  7. Dual Coding — словесное объяснение + визуальная опора (доска)
  8. Formative Assessment — постоянная проверка понимания
  9. Adaptive Difficulty — подстройка сложности под уровень ученика
  10. Emotional Scaffolding — поддержка мотивации и уверенности

Стратегии выбираются на основе:
  - Типа намерения ученика (IntentType)
  - Уровня понимания (UnderstandingLevel)
  - Текущего шага урока
  - Истории диалога
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from src.dialog.intent_classifier import IntentType


class UnderstandingLevel(Enum):
    """Уровень понимания ученика."""
    CONFUSED = "confused"         # не понял вообще
    UNCERTAIN = "uncertain"       # частично понял, но не уверен
    BASIC = "basic"               # понял основы, но путается в деталях
    PROFICIENT = "proficient"     # хорошо понял, может применять
    ADVANCED = "advanced"         # глубоко понял, может объяснять другим


class TeachingMethod(Enum):
    """Методы обучения."""
    DIRECT_EXPLANATION = "direct_explanation"
    SOCRATIC_QUESTIONS = "socratic_questions"
    SCAFFOLDED_GUIDANCE = "scaffolded_guidance"
    ANALOGY = "analogy"
    CONCRETE_EXAMPLE = "concrete_example"
    VISUAL_DEMONSTRATION = "visual_demonstration"
    RETRIEVAL_PRACTICE = "retrieval_practice"
    ELABORATIVE_QUESTIONS = "elaborative_questions"
    STEP_BACK = "step_back"
    ENCOURAGEMENT = "encouragement"
    DIFFICULTY_INCREASE = "difficulty_increase"
    DIFFICULTY_DECREASE = "difficulty_decrease"


@dataclass
class TeachingStrategy:
    """Рекомендуемая стратегия обучения."""
    method: TeachingMethod
    reason: str
    suggested_response_style: str  # кратко / подробно / с вопросом / с примером
    board_action: Optional[str] = None  # рекомендация по доске
    next_step_adjustment: int = 0  # -1 = вернуться назад, 0 = продолжить, +1 = ускориться
    confidence: float = 0.8


# ──────────────────────────────────────────────────────────────────────────
# Стратегии для каждого типа намерения
# ──────────────────────────────────────────────────────────────────────────

# Карта: IntentType -> UnderstandingLevel -> TeachingStrategy
STRATEGY_MAP: dict[tuple[IntentType, Optional[UnderstandingLevel]], TeachingStrategy] = {
    # ── Вопросы по теме ─────────────────────────────────────────────────
    (IntentType.ON_TOPIC_QUESTION, UnderstandingLevel.CONFUSED): TeachingStrategy(
        method=TeachingMethod.STEP_BACK,
        reason="Ученик задаёт вопрос по теме, но уровень понимания низкий — нужно вернуться назад",
        suggested_response_style="с примером и аналогией",
        board_action="show_definition",
        next_step_adjustment=-1,
    ),
    (IntentType.ON_TOPIC_QUESTION, UnderstandingLevel.UNCERTAIN): TeachingStrategy(
        method=TeachingMethod.SCAFFOLDED_GUIDANCE,
        reason="Ученик спрашивает — нужно поддержать, но не перегружать",
        suggested_response_style="подробно с примером",
        board_action=None,
        next_step_adjustment=0,
    ),
    (IntentType.ON_TOPIC_QUESTION, UnderstandingLevel.BASIC): TeachingStrategy(
        method=TeachingMethod.ELABORATIVE_QUESTIONS,
        reason="Ученик понимает основы — можно углубить через вопросы",
        suggested_response_style="с подводящим вопросом",
        board_action=None,
        next_step_adjustment=0,
    ),
    (IntentType.ON_TOPIC_QUESTION, UnderstandingLevel.PROFICIENT): TeachingStrategy(
        method=TeachingMethod.SOCRATIC_QUESTIONS,
        reason="Ученик хорошо понимает — можно углубить через сократовский метод",
        suggested_response_style="с вопросом для размышления",
        board_action=None,
        next_step_adjustment=0,
    ),
    (IntentType.ON_TOPIC_QUESTION, None): TeachingStrategy(
        method=TeachingMethod.DIRECT_EXPLANATION,
        reason="Нет данных об уровне понимания — даём прямой ответ",
        suggested_response_style="подробно с примером",
        board_action=None,
        next_step_adjustment=0,
    ),

    # ── Вопросы не по теме ──────────────────────────────────────────────
    (IntentType.OFF_TOPIC_QUESTION, None): TeachingStrategy(
        method=TeachingMethod.DIRECT_EXPLANATION,
        reason="Вопрос не по теме — кратко ответить и вернуться к уроку",
        suggested_response_style="кратко",
        board_action=None,
        next_step_adjustment=0,
    ),

    # ── Сигналы непонимания ─────────────────────────────────────────────
    (IntentType.CONFUSION_SIGNAL, UnderstandingLevel.CONFUSED): TeachingStrategy(
        method=TeachingMethod.ANALOGY,
        reason="Ученик полностью не понял — нужна новая аналогия или метафора",
        suggested_response_style="с аналогией из жизни",
        board_action="show_simple_formula",
        next_step_adjustment=-1,
    ),
    (IntentType.CONFUSION_SIGNAL, UnderstandingLevel.UNCERTAIN): TeachingStrategy(
        method=TeachingMethod.STEP_BACK,
        reason="Ученик запутался — вернуться на шаг назад",
        suggested_response_style="подробно с пошаговым объяснением",
        board_action=None,
        next_step_adjustment=-1,
    ),
    (IntentType.CONFUSION_SIGNAL, None): TeachingStrategy(
        method=TeachingMethod.SCAFFOLDED_GUIDANCE,
        reason="Ученик не понял — пошаговое объяснение с опорой",
        suggested_response_style="подробно с вопросами",
        board_action=None,
        next_step_adjustment=-1,
    ),

    # ── Правильный ответ ────────────────────────────────────────────────
    (IntentType.CORRECT_ANSWER, UnderstandingLevel.BASIC): TeachingStrategy(
        method=TeachingMethod.RETRIEVAL_PRACTICE,
        reason="Ученик ответил правильно на базовом уровне — закрепляем",
        suggested_response_style="с похвалой и уточняющим вопросом",
        board_action=None,
        next_step_adjustment=0,
    ),
    (IntentType.CORRECT_ANSWER, UnderstandingLevel.PROFICIENT): TeachingStrategy(
        method=TeachingMethod.ELABORATIVE_QUESTIONS,
        reason="Ученик ответил правильно — углубляем понимание",
        suggested_response_style="с вопросом «а почему именно так?»",
        board_action=None,
        next_step_adjustment=0,
    ),
    (IntentType.CORRECT_ANSWER, None): TeachingStrategy(
        method=TeachingMethod.RETRIEVAL_PRACTICE,
        reason="Правильный ответ — поощряем и проверяем глубину",
        suggested_response_style="с похвалой",
        board_action=None,
        next_step_adjustment=0,
    ),

    # ── Неправильный ответ ──────────────────────────────────────────────
    (IntentType.INCORRECT_ANSWER, UnderstandingLevel.CONFUSED): TeachingStrategy(
        method=TeachingMethod.STEP_BACK,
        reason="Ученик ошибся и не понимает — нужно вернуться к основе",
        suggested_response_style="с исправлением ошибки и аналогией",
        board_action="show_comparison",
        next_step_adjustment=-1,
    ),
    (IntentType.INCORRECT_ANSWER, None): TeachingStrategy(
        method=TeachingMethod.SCAFFOLDED_GUIDANCE,
        reason="Ученик ошибся, но уровне понимания достаточный — направляем",
        suggested_response_style="с подсказкой и направляющим вопросом",
        board_action=None,
        next_step_adjustment=0,
    ),

    # ── Просьба повторить ───────────────────────────────────────────────
    (IntentType.CLARIFICATION_REQUEST, None): TeachingStrategy(
        method=TeachingMethod.DIRECT_EXPLANATION,
        reason="Ученик просит повторить — повторяем по-другому",
        suggested_response_style="подробно иначе",
        board_action=None,
        next_step_adjustment=0,
    ),

    # ── Проверка вовлечённости ──────────────────────────────────────────
    (IntentType.ENGAGEMENT_CHECK, None): TeachingStrategy(
        method=TeachingMethod.ENCOURAGEMENT,
        reason="Ученик проверяет, слушает ли бот — подтверждаем присутствие",
        suggested_response_style="дружелюбно с продолжением",
        board_action=None,
        next_step_adjustment=0,
    ),

    # ── Заполнители ─────────────────────────────────────────────────────
    (IntentType.FILLER, None): TeachingStrategy(
        method=TeachingMethod.DIRECT_EXPLANATION,
        reason="Ученик заполняет паузу — можно продолжать",
        suggested_response_style="кратко",
        board_action=None,
        next_step_adjustment=0,
    ),

    # ── Разговор не по делу ─────────────────────────────────────────────
    (IntentType.OFF_TOPIC_CHAT, None): TeachingStrategy(
        method=TeachingMethod.DIRECT_EXPLANATION,
        reason="Разговор не по делу — мягко вернуть к теме",
        suggested_response_style="мягко с возвращением к теме",
        board_action=None,
        next_step_adjustment=0,
    ),
}


# ──────────────────────────────────────────────────────────────────────────
# Стратегии для уровней понимания
# ──────────────────────────────────────────────────────────────────────────

UNDERSTANDING_STRATEGIES: dict[UnderstandingLevel, TeachingStrategy] = {
    UnderstandingLevel.CONFUSED: TeachingStrategy(
        method=TeachingMethod.ANALOGY,
        reason="Ученик запутался — нужна новая аналогия или метафора",
        suggested_response_style="с простой аналогией из жизни",
        board_action="show_simple_example",
        next_step_adjustment=-1,
    ),
    UnderstandingLevel.UNCERTAIN: TeachingStrategy(
        method=TeachingMethod.SCAFFOLDED_GUIDANCE,
        reason="Ученик не уверен — нужна поддержка",
        suggested_response_style="с пошаговым объяснением",
        board_action=None,
        next_step_adjustment=0,
    ),
    UnderstandingLevel.BASIC: TeachingStrategy(
        method=TeachingMethod.RETRIEVAL_PRACTICE,
        reason="Ученик понимает основы — проверяем через вопросы",
        suggested_response_style="с проверочным вопросом",
        board_action=None,
        next_step_adjustment=0,
    ),
    UnderstandingLevel.PROFICIENT: TeachingStrategy(
        method=TeachingMethod.ELABORATIVE_QUESTIONS,
        reason="Ученик хорошо понимает — углубляем",
        suggested_response_style="с углубляющим вопросом",
        board_action=None,
        next_step_adjustment=0,
    ),
    UnderstandingLevel.ADVANCED: TeachingStrategy(
        method=TeachingMethod.DIFFICULTY_INCREASE,
        reason="Ученик продвинутый — можно усложнить",
        suggested_response_style="с дополнительным контекстом",
        board_action=None,
        next_step_adjustment=1,
    ),
}


# ──────────────────────────────────────────────────────────────────────────
# Функции выбора стратегии
# ──────────────────────────────────────────────────────────────────────────

def select_strategy(
    intent: IntentType,
    understanding: Optional[UnderstandingLevel] = None,
    step_index: int = 0,
    total_steps: int = 0,
    consecutive_correct: int = 0,
    consecutive_incorrect: int = 0,
) -> TeachingStrategy:
    """
    Выбрать оптимальную стратегию обучения.

    Args:
        intent: тип намерения ученика
        understanding: текущий уровень понимания
        step_index: индекс текущего шага (0-based)
        total_steps: общее количество шагов
        consecutive_correct: количество правильных ответов подряд
        consecutive_incorrect: количество неправильных ответов подряд
    """
    # 1. Проверяем точное совпадение (intent + understanding)
    key = (intent, understanding)
    if key in STRATEGY_MAP:
        strategy = STRATEGY_MAP[key]
    # 2. Проверяем с None (любой уровень)
    elif (intent, None) in STRATEGY_MAP:
        strategy = STRATEGY_MAP[(intent, None)]
    # 3. Используем стратегию по умолчанию для intent
    else:
        strategy = TeachingStrategy(
            method=TeachingMethod.DIRECT_EXPLANATION,
            reason="Стратегия по умолчанию",
            suggested_response_style="подробно",
        )

    # 4. Корректируем на основе паттернов
    strategy = _adjust_strategy(
        strategy,
        step_index=step_index,
        total_steps=total_steps,
        consecutive_correct=consecutive_correct,
        consecutive_incorrect=consecutive_incorrect,
    )

    return strategy


def _adjust_strategy(
    strategy: TeachingStrategy,
    step_index: int,
    total_steps: int,
    consecutive_correct: int,
    consecutive_incorrect: int,
) -> TeachingStrategy:
    """Скорректировать стратегию на основе контекста урока."""

    # Если ученик 3+ раза ответил правильно подряд — можно усложнить
    if consecutive_correct >= 3 and strategy.method != TeachingMethod.DIFFICULTY_INCREASE:
        strategy = TeachingStrategy(
            method=TeachingMethod.DIFFICULTY_INCREASE,
            reason=f"Ученик ответил правильно {consecutive_correct} раза подряд — можно усложнить",
            suggested_response_style="с дополнительным контекстом",
            next_step_adjustment=0,
            confidence=0.9,
        )

    # Если ученик 2+ раза ошибся подряд — нужно упростить
    if consecutive_incorrect >= 2 and strategy.method != TeachingMethod.DIFFICULTY_DECREASE:
        strategy = TeachingStrategy(
            method=TeachingMethod.DIFFICULTY_DECREASE,
            reason=f"Ученик ошибся {consecutive_incorrect} раза подряд — упрощаем",
            suggested_response_style="с простой аналогией",
            board_action="show_simple_example",
            next_step_adjustment=-1,
            confidence=0.9,
        )

    # Если урок почти закончился (последние 20%) — не углубляем
    if total_steps > 0 and step_index >= total_steps * 0.8:
        if strategy.method in (TeachingMethod.ELABORATIVE_QUESTIONS, TeachingMethod.DIFFICULTY_INCREASE):
            strategy = TeachingStrategy(
                method=TeachingMethod.RETRIEVAL_PRACTICE,
                reason="Урок почти закончился — закрепляем без углубления",
                suggested_response_style="с кратким повторением",
                next_step_adjustment=0,
                confidence=0.85,
            )

    return strategy


# ──────────────────────────────────────────────────────────────────────────
# Генерация промпта для LLM на основе стратегии
# ──────────────────────────────────────────────────────────────────────────

def build_strategy_prompt(strategy: TeachingStrategy) -> str:
    """
    Сгенерировать дополнительный инструктаж для LLM на основе выбранной стратегии.
    Вставляется в system prompt перед контекстом урока.
    """
    prompts = {
        TeachingMethod.DIRECT_EXPLANATION: (
            "Дай прямой, понятный ответ. Будь конкретной, приведи пример. "
            "Не перегружай деталями — ответ должен быть не длиннее 3-4 предложений."
        ),
        TeachingMethod.SOCRATIC_QUESTIONS: (
            "Не давай готовый ответ сразу. Задай 1-2 подводящих вопроса, "
            "чтобы ученик сам пришёл к ответу. Подскажи, если застопорится."
        ),
        TeachingMethod.SCAFFOLDED_GUIDANCE: (
            "Объясни пошагово, разбей на микрочасти. "
            "После каждого шага проверяй понимание: «Понятно?» или «Ясно до этого момента?»"
        ),
        TeachingMethod.ANALOGY: (
            "Придумай СВОЮ新鲜ую аналогию из повседневной жизни. "
            "Не используй шаблоны типа 'как конструктор LEGO' — найди что-то новое. "
            "Направления: кулинария, бытовая химия, технологии, спорт, музыка, игры, транспорт. "
            "Свяжи абстрактную концепцию с чем-то знакомым ученику 8-11 класса."
        ),
        TeachingMethod.CONCRETE_EXAMPLE: (
            "Приведи конкретный пример из реальной жизни или школьной программы. "
            "Покажи формулу или уравнение на доске."
        ),
        TeachingMethod.VISUAL_DEMONSTRATION: (
            "Отправь команду на доску (формулу, уравнение, схему). "
            "Пока ученик смотрит на доску — объясняй голосом, что на ней изображено."
        ),
        TeachingMethod.RETRIEVAL_PRACTICE: (
            "Попроси ученика вспомнить или повторить ключевое понятие. "
            "Задай вопрос: «Можешь повторить определение?» или «Какой вывод мы сделали?»"
        ),
        TeachingMethod.ELABORATIVE_QUESTIONS: (
            "Задай углубляющий вопрос: «А почему именно так?», «Что будет если...?», "
            "«Как это связано с...?». Помоги ученику увидеть связи между понятиями."
        ),
        TeachingMethod.STEP_BACK: (
            "Вернись на шаг назад. Объясни с самого начала, но по-другому. "
            "Используй более простые слова и другую аналогию."
        ),
        TeachingMethod.ENCOURAGEMENT: (
            "Поддержи ученика. Скажи что-то вроде: «Не переживай, это нормально путаться», "
            "«Ты хорошо справляешься», «Давай разберёмся вместе»."
        ),
        TeachingMethod.DIFFICULTY_INCREASE: (
            "Ученик справляется — можно дать задачу посложнее или задать углубляющий вопрос. "
            "Предложи: «Хочешь попробовать задачу посложнее?» или «А как думаешь, почему именно так?»"
        ),
        TeachingMethod.DIFFICULTY_DECREASE: (
            "Ученик путается — упрости объяснение. "
            "Используй более простые слова, короткие предложения, яркую аналогию. "
            "Не перегружай деталями."
        ),
    }

    return prompts.get(strategy.method, "")


# ──────────────────────────────────────────────────────────────────────────
# Оценка уровня понимания
# ──────────────────────────────────────────────────────────────────────────

def estimate_understanding(
    conversation_history: list[dict],
    current_response: str = "",
) -> UnderstandingLevel:
    """
    Оценить уровень понимания ученика на основе истории диалога.

    Args:
        conversation_history: список {"role": "student"/"bot", "text": "..."}
        current_response: текущая реплика ученика (дополнительно)
    """
    if not conversation_history:
        return UnderstandingLevel.BASIC

    # Анализируем последние реплики ученика
    student_messages = [
        m["text"] for m in conversation_history
        if m.get("role") == "student"
    ]

    if not student_messages:
        return UnderstandingLevel.BASIC

    # Считаем паттерны
    confusion_count = 0
    correct_count = 0
    question_count = 0
    short_answers = 0

    for msg in student_messages[-5:]:  # последние 5 реплик
        msg_lower = msg.lower()

        # Непонимание
        if any(p in msg_lower for p in ["не понял", "не понимаю", "сложно", "трудно", "ещё раз"]):
            confusion_count += 1

        # Правильные ответы (похвала от бота после ответа)
        # Проверяем следующее сообщение бота
        idx = student_messages.index(msg)
        if idx + 1 < len(conversation_history):
            next_msg = conversation_history[idx + 1]
            if next_msg.get("role") == "bot":
                bot_text = next_msg["text"].lower()
                if any(p in bot_text for p in ["верно", "правильно", "молодец", "отлично", "именно"]):
                    correct_count += 1

        # Вопросы
        if "?" in msg or any(w in msg_lower for w in ["что", "как", "почему", "зачем"]):
            question_count += 1

        # Короткие ответы (одно слово)
        if len(msg.split()) <= 2:
            short_answers += 1

    # Определяем уровень
    if confusion_count >= 2:
        return UnderstandingLevel.CONFUSED
    elif confusion_count == 1 and correct_count == 0:
        return UnderstandingLevel.UNCERTAIN
    elif correct_count >= 3:
        return UnderstandingLevel.PROFICIENT
    elif correct_count >= 1 and question_count >= 1:
        return UnderstandingLevel.BASIC
    elif question_count >= 2:
        return UnderstandingLevel.BASIC
    else:
        return UnderstandingLevel.BASIC
