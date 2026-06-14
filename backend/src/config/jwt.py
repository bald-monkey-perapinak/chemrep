"""
JWT Configuration — single source of truth for JWT secret and settings.

All modules (auth, sse, whiteboard) must import from here.
"""

import logging
import os
import secrets
import sys

logger = logging.getLogger(__name__)

# JWT secret — read once from env. If missing, generate and log a WARNING.
_jwt_secret = os.getenv("JWT_SECRET", "")
if not _jwt_secret:
    _is_prod = os.getenv("APP_ENV", "development").lower() in ("production", "prod")
    if _is_prod:
        logger.critical(
            "[JWT] JWT_SECRET не задан в продакшене! "
            "Задайте JWT_SECRET в .env для работы сервиса."
        )
        sys.exit(1)
    _jwt_secret = secrets.token_hex(32)
    logger.warning(
        "[JWT] JWT_SECRET не задан! Сгенерирован временный ключ. "
        "В продакшене задайте JWT_SECRET в .env!"
    )


def get_jwt_secret() -> str:
    return _jwt_secret


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MIN = 30
REFRESH_TOKEN_EXPIRE_D = 30
