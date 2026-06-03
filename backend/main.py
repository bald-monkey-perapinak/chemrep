"""
Точка входа FastAPI-приложения.
Запуск: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.knowledge import router as knowledge_router

app = FastAPI(
    title="ХимТьютор API",
    description="Backend для сервиса автоматизированных уроков по химии",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


# ── Роутеры ────────────────────────────────────────────────────────────────
app.include_router(knowledge_router, prefix="/api")

# По мере реализации подключать:
# from src.api.routes import auth, lessons, students, sessions
# app.include_router(auth.router,      prefix="/api/auth",      tags=["auth"])
# app.include_router(lessons.router,   prefix="/api/lessons",   tags=["lessons"])
# app.include_router(students.router,  prefix="/api/students",  tags=["students"])
# app.include_router(sessions.router,  prefix="/api/sessions",  tags=["sessions"])
