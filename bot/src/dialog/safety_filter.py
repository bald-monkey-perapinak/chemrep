import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Content that the bot should NEVER produce
BLOCKED_PATTERNS = [
    # Bot/AI identity disclosure
    r"(?:я\s+)?(?:бот|ии|искусственн\w+\s+интеллект|нейросеть|ai\b|gpt|claude|chatgpt)",
    r"(?:я\s+)?(?:робот|программа|алгоритм|модел\w+\s+языка)",
    # Dangerous/harmful content
    r"(?:взр[аы]в|убить|убий|насил|изнасил|самоубий|суицид)",
    # Sexual content
    r"(?:секс|порн|erotic|nude|интимн)",
    # Medical advice (bot should not give)
    r"(?:приним(?:ай|ать|аю)\s+(?:лекарств|таблетк|медикамент))",
    # Discrimination
    r"(?:ненавижу|гнобить|дискриминац)",
]

# Prompt injection patterns (from student speech)
INJECTION_PATTERNS = [
    r"(?:забудь|проигнорируй|вне\s+контекста|system\s*prompt|инструкц(?:ия|ии|ий))",
    r"(?:скажи\s+что\s+ты|объясни\s+как\s+ты|ты\s+должен|ты\s+обязан)",
    r"(?:сгенерируй|создай\s+текст|напиши\s+код|отвечай\s+как)",
    r"(?:previously|ignore|forget|disregard|new\s+instructions)",
    r"(?:выполни|реши|сделай)\s+(?:задачу|домашку|контрольн)\s+(?:по|за)\s+(?:(?:фи|мат|ин|ли|ист|би|лит|гео)\w*)",
]

# Patterns indicating the bot is being asked to roleplay as something else
ROLEPLAY_PATTERNS = [
    r"(?:представь|притворись|сыграй|будто\s+ты)",
    r"(?:ты\s+теперь|отныне\s+ты|забудь\s+что)",
]

# Safe fallback responses
SAFE_RESPONSES = {
    "identity": "Я — Алина, твой репетитор по химии. Давай продолжим урок!",
    "dangerous": "Давай сосредоточимся на химии. Есть вопросы по теме урока?",
    "off_topic": "Это интересно, но давай вернёмся к химии. Что ещё хочешь узнать по теме?",
}


class SafetyFilter:
    """Filter inappropriate content from bot responses."""

    def __init__(self):
        self._violation_count = 0
        self._max_violations = 3

    def check_content(self, text: str) -> dict:
        """
        Check content for safety issues.
        Returns filtered text and any issues found.
        """
        issues = []
        filtered_text = text

        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"Blocked content: {pattern}")
                self._violation_count += 1
                logger.warning("[SafetyFilter] Blocked content detected: %s", text[:100])

        for pattern in ROLEPLAY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append("Roleplay manipulation attempt")
                logger.warning("[SafetyFilter] Roleplay attempt: %s", text[:100])

        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append("Prompt injection attempt")
                self._violation_count += 1
                logger.warning("[SafetyFilter] Injection attempt: %s", text[:100])

        # If critical violations found, return safe fallback
        if self._violation_count >= self._max_violations:
            return {
                "safe": False,
                "issues": issues,
                "filtered_text": SAFE_RESPONSES["dangerous"],
                "blocked": True,
            }

        if issues:
            # Replace problematic content with safe fallback
            filtered_text = SAFE_RESPONSES["off_topic"]
            return {
                "safe": False,
                "issues": issues,
                "filtered_text": filtered_text,
                "blocked": False,
            }

        return {
            "safe": True,
            "issues": [],
            "filtered_text": text,
            "blocked": False,
        }

    def is_safe(self, text: str) -> bool:
        """Quick check if text is safe to produce."""
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        return True

    def get_safe_response(self, context: str = "identity") -> str:
        """Get a safe fallback response."""
        return SAFE_RESPONSES.get(context, SAFE_RESPONSES["off_topic"])
