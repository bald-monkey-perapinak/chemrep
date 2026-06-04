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
    poll_interval: int = field(
        default_factory=lambda: int(os.getenv("SCHEDULER_POLL_INTERVAL", "30"))
    )
    launch_offset: int = field(
        default_factory=lambda: int(os.getenv("BOT_LAUNCH_OFFSET_SEC", "60"))
    )
    missed_timeout: int = field(
        default_factory=lambda: int(os.getenv("BOT_MISSED_TIMEOUT_SEC", "600"))
    )
    max_concurrent_sessions: int = field(
        default_factory=lambda: int(os.getenv("BOT_MAX_CONCURRENT", "5"))
    )

    # ── VCS / Playwright ───────────────────────────────────────────────────
    # false  — использовать реальные Zoom/Yandex клиенты (нужен playwright)
    # true   — всегда использовать StubVCSClient (для CI, dev без браузера)
    vcs_stub_mode: bool = field(
        default_factory=lambda: os.getenv("VCS_STUB_MODE", "false").lower() == "true"
    )
    # Таймаут подключения к конференции (секунды)
    vcs_connect_timeout: int = field(
        default_factory=lambda: int(os.getenv("VCS_CONNECT_TIMEOUT", "60"))
    )

    # ── Внешние сервисы ────────────────────────────────────────────────────
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )
    elevenlabs_api_key: str = field(
        default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", "")
    )
    miro_access_token: str = field(
        default_factory=lambda: os.getenv("MIRO_ACCESS_TOKEN", "")
    )

    # ── Логирование ────────────────────────────────────────────────────────
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )


config = Config()
