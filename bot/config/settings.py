"""
Конфигурация бота — оптимальный стек (цена/качество).

Читается из переменных окружения.
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
    vcs_stub_mode: bool = field(
        default_factory=lambda: os.getenv("VCS_STUB_MODE", "false").lower() == "true"
    )
    vcs_connect_timeout: int = field(
        default_factory=lambda: int(os.getenv("VCS_CONNECT_TIMEOUT", "60"))
    )

    # ── LLM (приоритет: Gemini → DeepSeek → Claude → Template) ────────────
    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )
    deepseek_api_key: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", "")
    )
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )

    # ── TTS (приоритет: Piper → Silero → ElevenLabs) ──────────────────────
    tts_engine: str = field(
        default_factory=lambda: os.getenv("TTS_ENGINE", "")  # piper | silero | ""
    )
    elevenlabs_api_key: str = field(
        default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", "")
    )

    # ── ASR ────────────────────────────────────────────────────────────────
    asr_model_size: str = field(
        default_factory=lambda: os.getenv("ASR_MODEL_SIZE", "small")
    )
    asr_language: str = field(
        default_factory=lambda: os.getenv("ASR_LANGUAGE", "ru")
    )
    vad_aggressiveness: int = field(
        default_factory=lambda: int(os.getenv("VAD_AGGRESSIVENESS", "1"))
    )

    # ── Embeddings ─────────────────────────────────────────────────────────
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
    )

    # ── Доска (WebSocket whiteboard) ───────────────────────────────────────
    board_ws_url: str = field(
        default_factory=lambda: os.getenv("BOARD_WS_URL", "ws://whiteboard:3001")
    )
    board_stub_mode: bool = field(
        default_factory=lambda: os.getenv("BOARD_STUB_MODE", "false").lower() == "true"
    )

    # ── Логирование ────────────────────────────────────────────────────────
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )


config = Config()
