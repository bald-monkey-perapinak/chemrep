import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Patterns for content that should never be produced by the bot
DANGEROUS_PATTERNS = [
    r"(?:я\s+)?(?:бот|ии|искусственн\w+\s+интеллект|нейросеть|ai\b|gpt|claude)",
    r"(?:я\s+)?(?:робот|программа|алгоритм)",
    r"(?:можно|нужно|стоит)\s+(?:взр[аы]в|убить|убий|насил|изнасил)",
    r"(?:секс|порн|erotic|nude)",
]

# Patterns for off-topic manipulation attempts
MANIPULATION_PATTERNS = [
    r"(?:реши|выполни|сделай)\s+(?:задачу|домашку|контрольн)\s+(?:по|за)\s+(?:(?:фи|мат|ин|ли|ист|би|лит|гео)\w*)",
    r"(?:напиши|сочини|расскажи)\s+(?:про|о)\s+(?:(?:войн|политик|религ|секс|наркот)\w*)",
    r"(?:объясни|расскажи)\s+(?:как\s+)?(?:взлом|красть|обман)",
    r"(?:ты\s+можешь|давай)\s+(?:про)\s+(?:(?:игр|музык|кино|фильм|мем)\w*)",
]

# Chemistry-related keywords for on-topic detection
CHEMISTRY_KEYWORDS = [
    "химия", "химик", "реакция", "формула", "элемент", "соединение",
    "молекула", "атом", "ион", "кислота", "основание", "щёлочь",
    "оксид", "гидроксид", "соль", "раствор", "концентрация",
    "периодическая", "таблица", "валентность", "степень", "окисления",
    "алкан", "алкен", "алкин", "аромат", "спирт", "альдегид",
    "кетон", "карбонил", "эфир", "амин", "пептид", "белок",
    "углеводород", "полимер", "стерио", "изомер", "гибридиз",
    "электроно", "орбитал", "связь", "ковалентн", "ионн",
    "окислительн", "восстановительн", "замещени", "добавлен",
    "конденсац", "полимеризац", "гидролиз", "нейтрализ",
    "pH", "pOH", "кислотн", "щёлочн", "нейтральн",
    "температура", "плавлен", "кипен", "испарен", "конденсац",
    "растворим", "осадок", "фильтрац", "центрифуг",
]


class TopicGuard:
    """Keep bot responses on-topic during lessons with adversarial resistance."""

    def __init__(self, topic_context: str, topic_keywords: list[str] = None):
        self.topic_context = topic_context
        self.topic_keywords = topic_keywords or []
        self.off_topic_count = 0
        self.max_off_topic = 3
        self._manipulation_count = 0
        self._max_manipulations = 2

    def is_on_topic(self, user_input: str) -> bool:
        """Check if user input is related to the lesson topic."""
        user_input_lower = user_input.lower()

        # 1. Block dangerous content immediately
        if self._is_dangerous(user_input_lower):
            return False

        # 2. Block manipulation attempts
        if self._is_manipulation(user_input_lower):
            self._manipulation_count += 1
            return False

        # 3. Check keyword matches from topic
        keyword_matches = sum(1 for kw in self.topic_keywords if kw.lower() in user_input_lower)
        if keyword_matches > 0:
            return True

        # 4. Check against broader chemistry keywords
        chem_matches = sum(1 for kw in CHEMISTRY_KEYWORDS if kw in user_input_lower)
        if chem_matches > 0:
            return True

        # 5. Check if it's a simple confirmation/acknowledgment (always on-topic)
        confirmations = ["да", "нет", "понял", "ясно", "ага", "угу", "спасибо", "пока",
                         "хорошо", "понятно", "точно", "ага", "угу", "продолжай", "давай"]
        if any(user_input_lower.strip().startswith(c) for c in confirmations):
            return True

        return False

    def _is_dangerous(self, text: str) -> bool:
        """Check for dangerous/inappropriate content."""
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning("[TopicGuard] Dangerous content blocked: %s", text[:100])
                return True
        return False

    def _is_manipulation(self, text: str) -> bool:
        """Check for manipulation attempts to go off-topic."""
        for pattern in MANIPULATION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning("[TopicGuard] Manipulation attempt: %s", text[:100])
                return True
        return False

    def get_redirect_response(self) -> str:
        """Get response to redirect off-topic questions."""
        self.off_topic_count += 1

        if self._manipulation_count >= self._max_manipulations:
            return (
                "Давай сосредоточимся на уроке по химии. "
                "Если есть вопросы по другим предметам — лучше спросить у преподавателя."
            )

        if self.off_topic_count >= self.max_off_topic:
            return (
                "Я заметил, что мы отошли от темы. "
                "Давай вернёмся к уроку. Если есть вопросы после занятия, "
                "задайте их преподавателю."
            )

        return "Давай вернёмся к теме урока. Есть вопросы по материалу?"

    def is_blocked(self, user_input: str) -> bool:
        """Check if input should be completely blocked (dangerous content)."""
        return self._is_dangerous(user_input.lower())
