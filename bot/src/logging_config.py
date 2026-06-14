"""
Structured JSON logging for the bot.

Matches backend logging format for consistent log aggregation.
"""

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone

# Context variable for lesson correlation
lesson_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar('lesson_id', default=None)


class ContextFilter(logging.Filter):
    def filter(self, record):
        record.lesson_id = lesson_id_var.get()
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "component": "bot",
        }
        if getattr(record, "lesson_id", None) is not None:
            log_entry["lesson_id"] = record.lesson_id
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(ContextFilter())

    logging.root.handlers = [handler]
    logging.root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Silence noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)


def set_lesson_context(lesson_id: str | None) -> None:
    """Set the current lesson ID for log correlation."""
    lesson_id_var.set(lesson_id)
