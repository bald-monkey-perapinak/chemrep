"""
Точка входа FastAPI-приложения.
Запуск: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import os
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Загружаем .env из корня проекта (../.env)
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from src.api.versioned import versioned_router

from src.middleware.metrics import MetricsMiddleware
from src.middleware.rate_limit import RateLimitMiddleware
from src.middleware.request_id import RequestIDMiddleware
from src.middleware.body_limit import BodyLimitMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from src.api.routes.auth      import router as auth_router
from src.api.routes.knowledge  import router as knowledge_router
from src.api.routes.students   import router as students_router
from src.api.routes.lessons    import router as lessons_router
from src.api.routes.sessions   import router as sessions_router
from src.api.routes.voice      import router as voice_router
from src.api.routes.sse        import router as sse_router
from src.api.routes.training   import router as training_router
from src.api.routes.extract    import router as extract_router
from src.api.routes.consent    import router as consent_router


from src.utils.logging import setup_json_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_json_logging()
    from src.utils.s3 import ensure_bucket
    ensure_bucket()
    yield


APP_VERSION = os.getenv("APP_VERSION", "0.4.0")

app = FastAPI(
    title="ХимТьютор API",
    description="Backend для сервиса автоматизированных уроков по химии",
    version=APP_VERSION,
    lifespan=lifespan,
)

# CORS — разрешённые домены (через запятую в CORS_ORIGINS)
_cors_origins_str = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173"
)
_cors_origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()]

import logging as _logging
_cors_logger = _logging.getLogger("chemrep.cors")
_cors_logger.info("CORS allowed origins: %s", _cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_middleware(MetricsMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=30, window_seconds=60)
app.add_middleware(BodyLimitMiddleware, max_body_size=100 * 1024 * 1024)
app.add_middleware(RequestIDMiddleware)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": APP_VERSION}


@app.get("/metrics", tags=["system"])
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


app.include_router(versioned_router(auth_router))
app.include_router(versioned_router(knowledge_router))
app.include_router(versioned_router(students_router))
app.include_router(versioned_router(lessons_router))
app.include_router(versioned_router(sessions_router))
app.include_router(versioned_router(voice_router))
app.include_router(versioned_router(sse_router))
app.include_router(versioned_router(training_router))
app.include_router(versioned_router(extract_router))
app.include_router(versioned_router(consent_router))


@app.get("/api/health", tags=["system"])
async def api_health_compat():
    return {"status": "ok", "version": APP_VERSION}
