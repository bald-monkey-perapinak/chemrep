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
student_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar('student_id', default=None)
step_var: contextvars.ContextVar[int | None] = contextvars.ContextVar('step', default=None)


class ContextFilter(logging.Filter):
    def filter(self, record):
        record.lesson_id = lesson_id_var.get()
        record.student_id = student_id_var.get()
        record.step = step_var.get()
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
        if getattr(record, "student_id", None) is not None:
            log_entry["student_id"] = record.student_id
        if getattr(record, "step", None) is not None:
            log_entry["step"] = record.step
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


def set_lesson_context(lesson_id: str | None, student_id: str | None = None) -> None:
    """Set the current lesson ID for log correlation."""
    lesson_id_var.set(lesson_id)
    student_id_var.set(student_id)


def set_step_context(step: int | None) -> None:
    """Set the current lesson step for log correlation."""
    step_var.set(step)
