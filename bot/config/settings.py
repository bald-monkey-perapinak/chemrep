"""
Конфигурация бота — читается из переменных окружения.
"""

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    # ── База данных ────────────────────────────────────────────────────────
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql://chemrep:password@localhost:5432/chemrep",
        )
    )

    # ── Оркестратор ────────────────────────────────────────────────────────
    # Как часто проверять расписание (секунды)
    poll_interval: int = field(
        default_factory=lambda: int(os.getenv("SCHEDULER_POLL_INTERVAL", "30"))
    )
    # За сколько секунд до scheduled_at запускать бота
    launch_offset: int = field(
        default_factory=lambda: int(os.getenv("BOT_LAUNCH_OFFSET_SEC", "60"))
    )
    # Сколько секунд ждать ученика после scheduled_at прежде чем пометить MISSED
    missed_timeout: int = field(
        default_factory=lambda: int(os.getenv("BOT_MISSED_TIMEOUT_SEC", "600"))
    )
    # Максимальное количество одновременных сессий
    max_concurrent_sessions: int = field(
        default_factory=lambda: int(os.getenv("BOT_MAX_CONCURRENT", "5"))
    )

    # ── Внешние сервисы (заглушки — заполнить в .env) ─────────────────────
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )
    elevenlabs_api_key: str = field(
        default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", "")
    )
    miro_access_token: str = field(
        default_factory=lambda: os.getenv("MIRO_ACCESS_TOKEN", "")
    )
    zoom_api_key: str = field(
        default_factory=lambda: os.getenv("ZOOM_API_KEY", "")
    )

    # ── Логирование ────────────────────────────────────────────────────────
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )


# Синглтон
config = Config()
