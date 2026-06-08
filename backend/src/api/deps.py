"""
Реэкспорт зависимостей для обратной совместимости.
Полная реализация JWT-auth — в src/api/routes/auth.py.
"""
from src.api.routes.auth import get_current_teacher  # noqa: F401
