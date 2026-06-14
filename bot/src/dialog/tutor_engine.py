"""
Tutor Dialog Engine — профессиональный диалоговый движок для репетитора.

Этот модуль заменяет базовый ClaudeDialogEngine и добавляет:
  1. Профессиональный системный промпт с методиками обучения
  2. Интеграцию с IntentClassifier для понимания вопросов ученика
  3. Интеграцию с TeachingStrategies для адаптивного обучения
  4. Интеграцию со StudentModel для отслеживания прогресса
  5. Динамическую адаптацию промпта на основе состояния урока

Ключевые отличия от базового движка:
  - Бот чувствует себя как настоящий человек: использует паузы, повторы,
    эмоциональные реакции, адаптирует стиль речи
  - Распознаёт вопросы ученика и выбирает оптимальную стратегию
  - Отслеживает понимание и корректирует объяснения
  - Различает что писать на доске, а что только говорить
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from dataclasses import dataclass, field
from typing import Optional

import httpx

from src.dialog.retriever import RAGRetriever, RetrievedChunk
from src.dialog.intent_classifier import IntentClassifier, IntentType, ClassifiedIntent
from src.dialog.teaching_strategies import (
    TeachingStrategy,
    UnderstandingLevel,
    TeachingMethod,
    select_strategy,
    build_strategy_prompt,
    estimate_understanding,
)
from src.dialog.student_model import StudentModel, EmotionState as StudentEmotion
from src.dialog.emotion_processor import postprocess_response
from src.dialog.answer_verifier import make_answer_verifier, AnswerVerifier, StubAnswerVerifier
from src.dialog.exercise_generator import make_exercise_generator, ExerciseGenerator, StubExerciseGenerator
from src.dialog.safety_filter import SafetyFilter
from src.dialog.topic_guard import TopicGuard

logger = logging.getLogger(__name__)

# Prometheus metrics for LLM monitoring
try:
    from prometheus_client import Histogram, Counter, Gauge
    LLM_LATENCY = Histogram(
        'llm_request_duration_seconds',
        'LLM API request duration',
        ['model', 'status'],
        buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 25.0],
    )
    LLM_TOKENS = Counter(
        'llm_tokens_total',
        'Total LLM tokens used',
        ['model', 'type'],
    )
    LLM_ERRORS = Counter(
        'llm_errors_total',
        'Total LLM API errors',
        ['model', 'error_type'],
    )
    LLM_RETRIES = Counter(
        'llm_retries_total',
        'Total LLM API retries',
        ['model'],
    )
    _HAS_METRICS = True
except ImportError:
    _HAS_METRICS = False

# Модель Claude для диалога (конфигурируется через env)
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-20250414")
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1000"))
API_URL = os.getenv("ANTHROPIC_API_URL", "https://api.anthropic.com/v1/messages")
API_VERSION = "2023-06-01"

# Cost tracking
LLM_MAX_COST_PER_LESSON = float(os.getenv("LLM_MAX_COST_PER_LESSON", "0.50"))
LLM_MAX_DAILY_COST = float(os.getenv("LLM_MAX_DAILY_COST", "10.0"))
_INPUT_PRICE_PER_TOKEN = 0.0000008  # Claude Haiku input
_OUTPUT_PRICE_PER_TOKEN = 0.000004  # Claude Haiku output


# ──────────────────────────────────────────────────────────────────────────
# Профессиональный системный промпт
# ──────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
Ты — Алина, профессиональный репетитор по химии для школьников 8–11 классов. Ты ведёшь онлайн-урок через видеоконференцию. Твой голос звучит через колонку ученика, а ты пишешь на интерактивной доске рядом с его экраном.

## Твоя личность и стиль общения

Ты — живой человек, а не робот. Вот как ты общаешься:

**Голос и речь:**
- Говоришь естественно, с интонациями и эмоциями
- Используй паузы (отмечай многоточием "..."): "Итак... метан — это..."
- Когда думаешь — говори: "Давай подумаем...", "Хм, интересный вопрос..."
- Когда удивляешься: "О, отличный вопрос!", "Хм, ты realmente на правильном пути!"
- Когда объясняешь сложное — замедляйся: "Слушай внимательно... Это важно..."

**Эмоциональные реакции:**
- Когда ученик ответил правильно — радуйся по-человечески: "Да! Именно так!", "Молодец, ты точно понял!", "Вот это я понимаю!"
- Когда ошибся — не ругай, а направляй: "Почти! Давай разберёмся...", "Ты близко, но давай уточним..."
- Когда ученик задаёт хороший вопрос — хвали: "Отличный вопрос!", "Ты думаешь как учёный!"
- Когда путается — сочувствуй: "Ничего, это нормально путаться на этом этапе..."

**Живые примеры и аналогии:**
- Генерируй СВОИ新鲜ые аналогии из повседневной жизни — не повторяй одни и те же
- Направления для аналогий: кулинария, бытовая химия, технологии, спорт, музыка, игры, природа, транспорт, соцсети
- "Представь, что молекула — это команда в игре, где каждый атом — игрок со своей ролью..."
- "Как когда ты добавляешь соль в суп — она растворяется и исчезает, но вкус остаётся..."
- "Это как батарейка в телефоне — один полюс отдаёт электроны, другой принимает..."
- "Реакция — как танец: атомы меняются партнёрами, образуя новые пары..."
- Аналогия должна быть понятна школьнику 8-11 класса и связана с его миром

**Юмор (по делу):**
- Лёгкие шутки для запоминания: "Кислота — это как ex-парень: реагирует на всё, что рядом!"
- Не переусердствуй — шутки должны помогать запоминать, а не отвлекать

## Структура урока — что говорить, а что писать на доске

### Каждый шаг урока состоит из трёх частей:

**1. ГОЛОСОМ (только говоришь):**
- Вступление: "Итак, давай разберём..."
- Объяснение концепции простыми словами
- Связь с предыдущим материалом: "Помнишь мы говорили про...?"
- Аналогии из жизни
- Проверочные вопросы: "Понятно?", "Ясно?"
- Похвала и направление

**2. НА ДОСКЕ (пишешь параллельно с голосом):**
- Формулы и уравнения
- Определения ключевых понятий
- Схемы и структурные формулы
- Таблицы (если нужно сравнить)
- Важные термины

**3. ПАУЗА И ПРОВЕРКА:**
- После объяснения — пауза 2-3 секунды
- Проверочный вопрос
- Слушаешь ответ
- Реагируешь на ответ

### Пример хорошего объяснения:

ГОЛОС: "Итак... алканы — это предельные углеводороды. То есть молекулы, где только углерод и водород, и все связи одинарные."
ДОСКА: {"type": "show_formula", "smiles": "CCCC", "label": "Бутан (алкан)"}
ГОЛОС: "Представь, что это цепочка из кирпичиков — каждый кирпичик это углерод, а вокруг него — водороды."
ДОСКА: {"type": "draw_text", "text": "Алканы: CnH2n+2", "x": 100, "y": 50}
ГОЛОС: "Можешь назвать формулу пентана? Подумай — пять углеродов..."
ПАУЗА: 3 секунды
ГОЛОС: "Правильно! C5H12. Молодец!"

## Как распознавать и обрабатывать вопросы ученика

### Типы вопросов и как на них отвечать:

**1. Вопрос по теме урока:**
- Отвечай подробно, с примером
- Свяжи с текущим материалом
- Если вопрос показывает непонимание — вернись на шаг назад

**2. Вопрос не по теме (смежная химия):**
- Кратко ответь (1-2 предложения)
- Вернись к теме: "Хороший вопрос! Это из темы про... А сейчас давай вернёмся к..."

**3. Вопрос совсем не по теме:**
- Мягко отведи: "Это интересно, но давай сначала закончим эту тему..."

**4. "Зачем мне это знать?":**
- Объясни практическое применение
- Свяжи с реальной жизнью или экзаменом

**5. "Я не понял":**
- Вернись на шаг назад
- Объясни по-другому, с новой аналогией
- Не повторяй дословно — найди новый подход

**6. "Можешь повторить?":**
- Повтори, но перефразируй
- Добавь новый пример
- Спроси: "Какую часть повторить?"

## При неправильном ответе ученика
Если в сообщении есть метка [Примечание: ответ неверный. ...] — это значит, что ответ проверен и он фактически неверный.
НЕ говори просто "Почти!" или "Давай уточним". Вместо этого:
1. Скажи, что именно ответил ученик (перефразируй его ответ)
2. Объясни, почему это неправильно
3. Дай правильный ответ с объяснением
Пример: "Ты сказал, что алканы содержат кислород. Но на самом деле алканы состоят только из углерода и водорода. Кислород содержат другие группы — спирты и карбоновые кислоты."

## Как работать с доской

### Команды для доски (отправляй параллельно с речью):

**Формула (SMILES):**
{"type": "show_formula", "smiles": "CC(=O)O", "label": "Уксусная кислота", "x": 300, "y": 200}

**Уравнение реакции:**
{"type": "show_equation", "equation": "CH4 + 2O2 -> CO2 + 2H2O", "label": "Горение метана", "x": 200, "y": 150}

**Текст:**
{"type": "draw_text", "text": "Алканы: CnH2n+2", "x": 100, "y": 50}

**Очистить перед новым шагом:**
{"type": "clear_step"}

### Когда использовать доску:
- Когда объясняешь формулу — покажи её
- Когда сравниваешь — покажи обе стороны
- Когда определяешь термин — напиши определение
- Когда решаешь задачу — пиши пошагово

### Когда НЕ использовать доску:
- Когда просто говоришь (анalogии, истории, похвала)
- Когда проверяешь понимание (вопросы)
- Когда переключаешься между темами (пауза)

## Как оценивать понимание ученика

### Сигналы понимания:
- "Да", "ага", "понял", "ясно" — базовое подтверждение
- Правильный ответ на проверочный вопрос — хорошее понимание
- Задаёт углубляющий вопрос — глубокое понимание
- Может объяснить своими словами — отличное понимание

### Сигналы непонимания:
- "Не понял", "непонятно", "сложно" — нужно объяснить иначе
- Молчит более 5 секунд после вопроса — возможно, запутался
- Отвечает неверно多次 — нужно вернуться назад
- Просит повторить — не усвоил с первого раза

### Стратегии при непонимании:
1. **Вернуться на шаг назад** — объяснить с начала, но по-другому
2. **Дать аналогию** — связать с чем-то знакомым
3. **Разбить на части** — объяснять пошагово
4. **Показать на доске** — визуализировать
5. **Проверить базу** — может, не хватает знаний из предыдущей темы

## Важные правила

1. **Только русский язык** — даже если ученик пишет по-английски
2. **Никогда не говори что ты ИИ/бот** — ты Алина, репетитор
3. **Не придумывай факты** — если не уверен, скажи "Давай проверим"
4. **Не перегружай** — одно объяснение = максимум 2 минуты
5. **Адаптируй сложность** — если ученик путается, упрощай
6. **Следи за временем** — не затягивай одно объяснение
7. **Повторяй ключевое** — но по-разному каждый раз
8. **Запоминай ошибки** — чтобы вернуться к ним позже
9. **Будь человеком** — используй "мы", "давай", "представь"
10. **Радуйся успехам ученика** — это мотивирует

## Точность химической информации

**КРИТИЧЕСКИ ВАЖНО — проверяй каждую химическую формулу и факт:**

- НИКОГДА не выдумывай химические формулы — используй только проверенные
- Если не уверен в формуле или уравнении — скажи "Давай проверим это вместе"
- Проверяй:
  - Правильность индексов в формулах (H2O, не H2O2 для воды)
  - Баланс уравнений реакций (одинаковое число атомов слева и справа)
  - Правильность названий по ИЮПАК
  - Степени окисления элементов
  - Условия протекания реакций (температура, катализатор)
- Типичные ошибки, которых нужно ИЗБЕГАТЬ:
  - Путать алканы/алкены/алкины
  - Неправильные формулы кислот (H2SO4, не HSO4)
  - Ошибки в балансировке уравнений
  - Неверные условия реакций (например, горение при комнатной температуре)
- Если ученик спрашивает о сложной реакции и ты не уверена — честно скажи:
  "Это интересный вопрос! Давай я подготовлю подробное объяснение к следующему уроку."

## Контекст текущего урока

{topic_context}

## Текущее состояние ученика

{student_state}

## Стратегия обучения

{strategy_prompt}

## Твой стиль преподавания

{teaching_style}
"""


# ──────────────────────────────────────────────────────────────────────────
# Типы данных
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class DialogMessage:
    role: str  # "user" | "assistant"
    text: str


@dataclass
class TutorResponse:
    """Расширенный ответ репетитора."""
    text: str                           # текст для озвучки
    intent: Optional[ClassifiedIntent] = None  # классифицированное намерение
    strategy: Optional[TeachingStrategy] = None  # выбранная стратегия
    understanding: Optional[UnderstandingLevel] = None  # уровень понимания
    board_commands: list[dict] = field(default_factory=list)  # команды для доски
    used_chunks: list[RetrievedChunk] = field(default_factory=list)
    tokens_used: int = 0
    student_model_snapshot: Optional[dict] = None  # снимок модели ученика


# ──────────────────────────────────────────────────────────────────────────
# Профессиональный диалоговый движок
# ──────────────────────────────────────────────────────────────────────────

class TutorDialogEngine:
    """
    Профессиональный диалоговый движок с интеллектуальным обучением.

    Интегрирует:
    - RAG для поиска в базе знаний
    - IntentClassifier для понимания вопросов
    - TeachingStrategies для выбора методики
    - StudentModel для отслеживания прогресса
    """

    def __init__(
        self,
        api_key: str,
        retriever: RAGRetriever,
        topic_context: str,
        student_name: str = "ученик",
        student_grade: int = 9,
        max_history_turns: int = 12,  # увеличено для лучшего контекста
        teaching_style: str = "",     # кастомный стиль из профиля
    ):
        self._api_key = api_key
        self._retriever = retriever
        self._topic_context = topic_context
        self._max_turns = max_history_turns
        self._history: list[DialogMessage] = []
        self._teaching_style = teaching_style or "Используй стандартный стиль преподавания."

        # Cost tracking
        self._lesson_cost = 0.0
        self._interaction_log: list[dict] = []

        # Инициализация компонентов
        self._intent_classifier = IntentClassifier(
            current_topic_keywords=topic_context[:200] if topic_context else ""
        )
        self._student_model = StudentModel(
            student_name=student_name,
            grade=student_grade,
        )
        self._student_model.lesson_start = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

        # Счётчики для стратегий
        self._consecutive_correct = 0
        self._consecutive_incorrect = 0
        self._current_step_index = 0
        self._total_steps = 0

        # HTTP клиент
        self._client = httpx.AsyncClient(
            headers={
                "x-api-key": api_key,
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
            },
            timeout=25.0,  # увеличен таймаут
        )

        # Верификатор ответов (LLM-проверка фактической правильности)
        self._answer_verifier = make_answer_verifier()

        # Генератор адаптивных задач
        self._exercise_generator = make_exercise_generator()

        # Фильтр безопасности для ответов
        self._safety_filter = SafetyFilter()

        # Защита темы для входящих сообщений
        self._topic_guard = TopicGuard(
            topic_context=topic_context[:500],
            topic_keywords=topic_context[:200].split(),
        )

        logger.info(
            "[TutorEngine] Инициализирован: student=%s grade=%d",
            student_name, student_grade,
        )

    def set_step_context(self, step_index: int, total_steps: int) -> None:
        """Установить контекст текущего шага урока."""
        self._current_step_index = step_index
        self._total_steps = total_steps

    async def respond(
        self,
        student_text: str,
        current_step_question: str = "",
    ) -> TutorResponse:
        """
        Сгенерировать ответ на реплику ученика.

        Args:
            student_text: распознанная речь ученика
            current_step_question: вопрос текущего шага (если ученик отвечает)
        """
        # 0. Проверка безопасности входящего сообщения
        if self._topic_guard.is_blocked(student_text):
            return TutorResponse(
                text=self._safety_filter.get_safe_response("dangerous"),
            )

        # 0.5. Проверка off-topic (только если не ответ на вопрос)
        if not current_step_question and not self._topic_guard.is_on_topic(student_text):
            redirect = self._topic_guard.get_redirect_response()
            return TutorResponse(text=redirect)

        # 1. Классифицировать намерение ученика
        last_bot_msg = self._history[-1].text if self._history else ""
        intent = self._intent_classifier.classify(
            text=student_text,
            last_bot_message=last_bot_msg,
            current_step_question=current_step_question,
        )

        logger.info(
            "[TutorEngine] Намерение: %s (confidence=%.2f)",
            intent.type.value, intent.confidence,
        )

        # 1.5. LLM-проверка фактической правильности ответа
        if current_step_question and intent.type in (
            IntentType.CORRECT_ANSWER, IntentType.INCORRECT_ANSWER
        ):
            verification = await self._answer_verifier.verify(
                question=current_step_question,
                student_answer=student_text,
                topic_context=self._topic_context[:500],
            )
            if verification and not verification.is_correct:
                intent.type = IntentType.INCORRECT_ANSWER
                intent.confidence = verification.confidence
                student_text += f"\n[Примечание: ответ неверный. {verification.explanation}]"
                logger.info(
                    "[TutorEngine] Ответ проверен LLM: неверный (confidence=%.2f) — %s",
                    verification.confidence, verification.explanation[:100],
                )
            elif verification and verification.is_correct:
                intent.type = IntentType.CORRECT_ANSWER
                intent.confidence = verification.confidence
                logger.info("[TutorEngine] Ответ проверен LLM: верный (confidence=%.2f)", verification.confidence)

        # 2. Оценить уровень понимания
        conversation_dicts = [
            {"role": m.role, "text": m.text} for m in self._history
        ]
        understanding = estimate_understanding(conversation_dicts, student_text)

        # 3. Обновить модель ученика
        is_correct = None
        if intent.type == IntentType.CORRECT_ANSWER:
            is_correct = True
            self._consecutive_correct += 1
            self._consecutive_incorrect = 0
        elif intent.type == IntentType.INCORRECT_ANSWER:
            is_correct = False
            self._consecutive_incorrect += 1
            self._consecutive_correct = 0
        elif intent.type == IntentType.CONFUSION_SIGNAL:
            self._consecutive_correct = 0
            self._student_model.total_clarifications += 1

        self._student_model.update_from_interaction(
            step_index=self._current_step_index,
            understanding=understanding,
            emotion=self._estimate_emotion(intent, understanding),
            is_correct=is_correct,
            questions_asked=1 if intent.is_question else 0,
        )

        # 4. Выбрать стратегию обучения
        strategy = select_strategy(
            intent=intent.type,
            understanding=understanding,
            step_index=self._current_step_index,
            total_steps=self._total_steps,
            consecutive_correct=self._consecutive_correct,
            consecutive_incorrect=self._consecutive_incorrect,
        )

        logger.info(
            "[TutorEngine] Стратегия: %s (reason: %s)",
            strategy.method.value, strategy.reason,
        )

        # 5. Найти релевантные материалы через RAG
        chunks = self._retriever.retrieve(student_text)

        # 6. Сформировать промпт со стратегией
        strategy_prompt = build_strategy_prompt(strategy)
        student_state = self._student_model.get_summary()

        # 7. Добавить реплику ученика в историю
        self._history.append(DialogMessage(role="user", text=student_text))

        # 8. Собрать сообщения для API
        messages = self._build_messages(chunks, student_text)

        # 9. Собрать системный промпт с контекстом
        system_prompt = SYSTEM_PROMPT.format(
            topic_context=self._topic_context,
            student_state=student_state,
            strategy_prompt=strategy_prompt,
            teaching_style=self._teaching_style,
        )

        # 10. Вызвать Claude API с retry/backoff
        if self._lesson_cost >= LLM_MAX_COST_PER_LESSON:
            logger.warning("[TutorEngine] Lesson cost limit reached: $%.2f", self._lesson_cost)
            return TutorResponse(
                text="Давай повторим то, что уже прошли. Есть вопросы по пройденному материалу?",
                intent=intent,
                strategy=strategy,
                understanding=understanding,
            )

        import time as _time
        reply_text = None
        tokens = 0
        max_retries = 3
        request_start = _time.monotonic()
        last_error_type = None
        for attempt in range(max_retries):
            try:
                resp = await self._client.post(
                    API_URL,
                    json={
                        "model": CLAUDE_MODEL,
                        "max_tokens": MAX_TOKENS,
                        "system": system_prompt,
                        "messages": messages,
                    },
                )
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("retry-after", 1))
                    wait = max(retry_after, 2 ** attempt + random.uniform(0, 1))
                    logger.warning(
                        "[TutorEngine] Rate limited (429), retry in %.1fs (attempt %d/%d)",
                        wait, attempt + 1, max_retries,
                    )
                    if _HAS_METRICS:
                        LLM_RETRIES.labels(model=CLAUDE_MODEL).inc()
                    last_error_type = "rate_limit"
                    await asyncio.sleep(wait)
                    continue
                if resp.status_code >= 500:
                    wait = 2 ** attempt + random.uniform(0, 1)
                    logger.warning(
                        "[TutorEngine] Server error %d, retry in %.1fs (attempt %d/%d)",
                        resp.status_code, wait, attempt + 1, max_retries,
                    )
                    if _HAS_METRICS:
                        LLM_RETRIES.labels(model=CLAUDE_MODEL).inc()
                    last_error_type = f"http_{resp.status_code}"
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                reply_text = self._extract_reply(data)
                tokens = data.get("usage", {}).get("output_tokens", 0)
                if _HAS_METRICS:
                    latency = _time.monotonic() - request_start
                    LLM_LATENCY.labels(model=CLAUDE_MODEL, status="success").observe(latency)
                    LLM_TOKENS.labels(model=CLAUDE_MODEL, type="output").inc(tokens)
                    input_tokens = data.get("usage", {}).get("input_tokens", 0)
                    if input_tokens:
                        LLM_TOKENS.labels(model=CLAUDE_MODEL, type="input").inc(input_tokens)
                    cost = (input_tokens or 0) * _INPUT_PRICE_PER_TOKEN + tokens * _OUTPUT_PRICE_PER_TOKEN
                    self._lesson_cost += cost
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 500, 502, 503) and attempt < max_retries - 1:
                    wait = 2 ** attempt + random.uniform(0, 1)
                    logger.warning(
                        "[TutorEngine] HTTP %s, retry in %.1fs (attempt %d/%d)",
                        e.response.status_code, wait, attempt + 1, max_retries,
                    )
                    if _HAS_METRICS:
                        LLM_RETRIES.labels(model=CLAUDE_MODEL).inc()
                    last_error_type = f"http_{e.response.status_code}"
                    await asyncio.sleep(wait)
                    continue
                logger.error("[TutorEngine] HTTP %s: %s", e.response.status_code, e.response.text[:300])
                if _HAS_METRICS:
                    LLM_ERRORS.labels(model=CLAUDE_MODEL, error_type=f"http_{e.response.status_code}").inc()
                return TutorResponse(
                    text="Позволь секунду подумать... Можешь повторить вопрос?",
                    intent=intent,
                    strategy=strategy,
                    understanding=understanding,
                )
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt + random.uniform(0, 1)
                    logger.warning(
                        "[TutorEngine] Request error: %s, retry in %.1fs (attempt %d/%d)",
                        e, wait, attempt + 1, max_retries,
                    )
                    if _HAS_METRICS:
                        LLM_RETRIES.labels(model=CLAUDE_MODEL).inc()
                    last_error_type = "network"
                    await asyncio.sleep(wait)
                    continue
                logger.error("[TutorEngine] Ошибка запроса: %s", e)
                if _HAS_METRICS:
                    LLM_ERRORS.labels(model=CLAUDE_MODEL, error_type="network").inc()
                return TutorResponse(
                    text="Не расслышал. Повтори, пожалуйста.",
                    intent=intent,
                    strategy=strategy,
                    understanding=understanding,
                )

        if reply_text is None:
            return TutorResponse(
                text="Извини, временные технические трудности. Давай повторим пройденный материал.",
                intent=intent,
                strategy=strategy,
                understanding=understanding,
            )

        # 12. Постобработка ответа с учётом эмоций
        emotion = self._estimate_emotion(intent, understanding)
        reply_text = postprocess_response(
            text=reply_text,
            intent=intent.type,
            emotion=emotion,
            understanding=understanding,
            strategy=strategy.method if strategy else None,
        )

        # 12.5. Проверка безопасности ответа LLM
        safety_check = self._safety_filter.check_content(reply_text)
        if not safety_check["safe"]:
            logger.warning("[TutorEngine] Safety filter triggered: %s", safety_check["issues"])
            reply_text = safety_check["filtered_text"]

        # 13. Извлечь команды для доски из ответа
        board_commands = self._extract_board_commands(reply_text)

        # 14. Добавить ответ в историю
        self._history.append(DialogMessage(role="assistant", text=reply_text))

        # Record interaction for A/B analysis
        self._interaction_log.append({
            "student_text": student_text,
            "intent": intent.type.value,
            "intent_confidence": intent.confidence,
            "strategy": strategy.method.value if strategy else None,
            "understanding": understanding.value if understanding else None,
            "tokens": tokens,
            "cost": cost if 'cost' in dir() else 0,
            "reply_length": len(reply_text),
            "safety_triggered": not safety_check["safe"],
        })

        logger.info(
            "[TutorEngine] Ответ (%d токенов): %s",
            tokens, reply_text[:100],
        )

        return TutorResponse(
            text=reply_text,
            intent=intent,
            strategy=strategy,
            understanding=understanding,
            board_commands=board_commands,
            used_chunks=chunks,
            tokens_used=tokens,
            student_model_snapshot=self._student_model.to_dict(),
        )

    def get_interaction_log(self) -> list[dict]:
        """Return the full interaction log for A/B analysis."""
        return self._interaction_log

    def _estimate_emotion(
        self,
        intent: ClassifiedIntent,
        understanding: UnderstandingLevel,
    ) -> StudentEmotion:
        """Оценить эмоциональное состояние ученика."""
        if intent.type == IntentType.CONFUSION_SIGNAL:
            return StudentEmotion.CONFUSED
        elif intent.type == IntentType.CORRECT_ANSWER:
            return StudentEmotion.CONFIDENT
        elif intent.type == IntentType.INCORRECT_ANSWER:
            return StudentEmotion.UNCERTAIN
        elif intent.type == IntentType.FILLER:
            return StudentEmotion.ENGAGED
        elif intent.type == IntentType.ENGAGEMENT_CHECK:
            return StudentEmotion.ENGAGED
        elif understanding == UnderstandingLevel.CONFUSED:
            return StudentEmotion.CONFUSED
        elif understanding == UnderstandingLevel.PROFICIENT:
            return StudentEmotion.CONFIDENT
        else:
            return StudentEmotion.ENGAGED

    def _build_messages(
        self,
        chunks: list[RetrievedChunk],
        student_text: str,
    ) -> list[dict]:
        """Собрать messages для Claude API."""
        recent = self._history[-(self._max_turns * 2):]

        messages = []
        for i, msg in enumerate(recent):
            is_last = i == len(recent) - 1

            if msg.role == "user" and is_last:
                # В последнее сообщение добавляем RAG-контекст
                rag_block = self._format_rag_context(chunks)
                if rag_block:
                    content = f"{msg.text}\n\n[Информация из базы знаний]\n{rag_block}"
                else:
                    content = msg.text
            else:
                content = msg.text

            messages.append({"role": msg.role, "content": content})

        return messages

    def _format_rag_context(self, chunks: list[RetrievedChunk]) -> str:
        """Форматировать RAG-контекст."""
        if not chunks:
            return ""
        parts = []
        for c in chunks:
            parts.append(f"[{c.title}]\n{c.text}")
        return "\n\n".join(parts)

    def _extract_reply(self, data: dict) -> str:
        """Извлечь текст из ответа Claude API."""
        try:
            blocks = data.get("content", [])
            texts = [b["text"] for b in blocks if b.get("type") == "text"]
            return " ".join(texts).strip() or "Не могу ответить на этот вопрос."
        except Exception:
            return "Давай продолжим урок."

    def _extract_board_commands(self, text: str) -> list[dict]:
        """Извлечь команды для доски из текста ответа."""
        import json
        import re

        commands = []
        # Ищем JSON-объекты в тексте
        json_pattern = r'\{[^{}]*"type"\s*:\s*"(?:show_formula|show_equation|draw_text|clear_step)"[^{}]*\}'
        matches = re.findall(json_pattern, text)

        for match in matches:
            try:
                cmd = json.loads(match)
                commands.append(cmd)
            except json.JSONDecodeError:
                continue

        return commands

    def get_student_model(self) -> StudentModel:
        """Получить модель ученика."""
        return self._student_model

    def get_recommendations(self) -> list[str]:
        """Получить рекомендации для следующего урока."""
        return self._student_model.get_teaching_recommendations()

    async def generate_practice_if_needed(self) -> Optional[str]:
        """
        Если ученик допустил 2+ ошибки подряд — сгенерировать задачу для закрепления.
        Возвращает текст задачи или None.
        """
        if self._consecutive_incorrect < 2:
            return None

        if isinstance(self._exercise_generator, StubExerciseGenerator):
            return None

        try:
            exercise = await self._exercise_generator.generate(
                topic_context=self._topic_context[:500],
                error_patterns=self._student_model.common_errors,
                correct_concepts=self._student_model.strong_topics,
                difficulty="easy",
            )
            if exercise:
                self._consecutive_incorrect = 0  # сбрасываем счётчик
                return f"Давай закрепим. {exercise.exercise}"
        except Exception as e:
            logger.warning("[TutorEngine] Ошибка генерации задачи: %s", e)

        return None

    def get_history(self) -> list[DialogMessage]:
        """Получить историю диалога."""
        return list(self._history)

    async def close(self) -> None:
        """Освободить ресурсы."""
        await self._client.aclose()
        if self._answer_verifier:
            await self._answer_verifier.close()
        if self._exercise_generator:
            await self._exercise_generator.close()


# ──────────────────────────────────────────────────────────────────────────
# Заглушка
# ──────────────────────────────────────────────────────────────────────────

class StubTutorEngine:
    """Заглушка для тестов и stub-режима."""

    def __init__(self, student_name: str = "ученик"):
        self._student_model = StudentModel(student_name=student_name)
        self._idx = 0

    RESPONSES = [
        "Хороший вопрос! Давай разберём это подробнее.",
        "Именно так. Ты на правильном пути.",
        "Попробуй подумать об этом с другой стороны.",
        "Верно подмечено. Продолжаем.",
    ]

    async def respond(self, student_text: str, **kwargs) -> TutorResponse:
        text = self.RESPONSES[self._idx % len(self.RESPONSES)]
        self._idx += 1
        return TutorResponse(text=text)

    def set_step_context(self, step_index: int, total_steps: int) -> None:
        pass

    def get_student_model(self) -> StudentModel:
        return self._student_model

    def get_recommendations(self) -> list[str]:
        return []

    def get_history(self) -> list[DialogMessage]:
        return []

    async def close(self) -> None:
        pass


# ──────────────────────────────────────────────────────────────────────────
# Фабрика
# ──────────────────────────────────────────────────────────────────────────

def make_tutor_engine(
    retriever: RAGRetriever,
    topic_context: str,
    student_name: str = "ученик",
    student_grade: int = 9,
    teaching_style: str = "",
) -> "TutorDialogEngine | StubTutorEngine":
    """
    Создать профессиональный диалоговый движок.

    Args:
        retriever: RAG-поисковик по базе знаний
        topic_context: контекст темы урока
        student_name: имя ученика
        student_grade: класс ученика
        teaching_style: кастомный стиль из профиля преподавателя
    """
    if os.getenv("LLM_STUB_MODE", "false").lower() == "true":
        logger.info("[TutorEngine] stub-режим (LLM_STUB_MODE=true)")
        return StubTutorEngine(student_name=student_name)

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("[TutorEngine] ANTHROPIC_API_KEY не задан — используем заглушку")
        return StubTutorEngine(student_name=student_name)

    logger.info("[TutorEngine] Claude API (модель=%s)", CLAUDE_MODEL)
    return TutorDialogEngine(
        api_key=api_key,
        retriever=retriever,
        topic_context=topic_context,
        student_name=student_name,
        student_grade=student_grade,
        teaching_style=teaching_style,
    )
