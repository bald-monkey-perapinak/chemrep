"""
Точка входа FastAPI-приложения.
Запуск: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.auth      import router as auth_router
from src.api.routes.knowledge  import router as knowledge_router
from src.api.routes.students   import router as students_router
from src.api.routes.lessons    import router as lessons_router
from src.api.routes.sessions   import router as sessions_router
from src.api.routes.voice      import router as voice_router
from src.api.routes.sse        import router as sse_router

app = FastAPI(
    title="ХимТьютор API",
    description="Backend для сервиса автоматизированных уроков по химии",
    version="0.2.0",
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


app.include_router(auth_router,      prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(students_router,  prefix="/api")
app.include_router(lessons_router,   prefix="/api")
app.include_router(sessions_router,  prefix="/api")
app.include_router(voice_router,     prefix="/api")
app.include_router(sse_router,       prefix="/api")
