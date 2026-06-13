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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.middleware.rate_limit import RateLimitMiddleware
from src.api.routes.auth      import router as auth_router
from src.api.routes.knowledge  import router as knowledge_router
from src.api.routes.students   import router as students_router
from src.api.routes.lessons    import router as lessons_router
from src.api.routes.sessions   import router as sessions_router
from src.api.routes.voice      import router as voice_router
from src.api.routes.sse        import router as sse_router
from src.api.routes.training   import router as training_router
from src.api.routes.extract    import router as extract_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.utils.s3 import ensure_bucket
    ensure_bucket()
    yield


app = FastAPI(
    title="ХимТьютор API",
    description="Backend для сервиса автоматизированных уроков по химии",
    version="0.3.0",
    lifespan=lifespan,
)

# CORS — разрешённые домены (через запятую в CORS_ORIGINS)
_cors_origins_str = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,https://chemrep.local"
)
_cors_origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware, max_requests=30, window_seconds=60)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": "0.3.0"}


app.include_router(auth_router,      prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(students_router,  prefix="/api")
app.include_router(lessons_router,   prefix="/api")
app.include_router(sessions_router,  prefix="/api")
app.include_router(voice_router,     prefix="/api")
app.include_router(sse_router,       prefix="/api")
app.include_router(training_router,  prefix="/api")
app.include_router(extract_router,  prefix="/api")
