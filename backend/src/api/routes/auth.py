"""
Auth API — регистрация, вход, профиль преподавателя.

POST /api/auth/register  — создать аккаунт
POST /api/auth/login     — получить JWT-токен
GET  /api/auth/me        — профиль текущего преподавателя
PATCH /api/auth/me       — обновить профиль (имя, платформа по умолчанию)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from src.db.base import get_db
from src.models.teacher import Teacher

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Конфиг JWT ────────────────────────────────────────────────────────────
import os
SECRET_KEY      = os.getenv("JWT_SECRET", "change-me-in-production-please")
ALGORITHM       = "HS256"
TOKEN_EXPIRE_H  = 24 * 7   # 7 дней

pwd_ctx    = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2     = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ── Схемы ─────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email:      EmailStr
    password:   str = Field(..., min_length=8)
    full_name:  str = Field(..., min_length=2)

class LoginResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"

class TeacherOut(BaseModel):
    id:                    str
    email:                 str
    full_name:             str
    subject:               str
    default_vcs_platform:  str
    voice_model_ready:     bool

    class Config:
        from_attributes = True

class ProfileUpdate(BaseModel):
    full_name:             Optional[str] = None
    subject:               Optional[str] = None
    default_vcs_platform:  Optional[str] = None


# ── Вспомогательные функции ───────────────────────────────────────────────

def _hash(password: str) -> str:
    return pwd_ctx.hash(password)

def _verify(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def _make_token(teacher_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_H)
    return jwt.encode({"sub": teacher_id, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_teacher(
    token: str = Depends(oauth2),
    db:    Session = Depends(get_db),
) -> Teacher:
    """JWT-зависимость — используется во всех защищённых роутерах."""
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Недействительный токен",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload    = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        teacher_id = payload.get("sub")
        if not teacher_id:
            raise cred_exc
    except JWTError:
        raise cred_exc

    teacher = db.query(Teacher).filter(
        Teacher.id == teacher_id,
        Teacher.is_active == True,  # noqa: E712
    ).first()
    if not teacher:
        raise cred_exc
    return teacher


# ── Эндпоинты ─────────────────────────────────────────────────────────────

@router.post("/register", response_model=TeacherOut, status_code=201,
             summary="Зарегистрировать преподавателя")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(Teacher).filter(Teacher.email == data.email).first():
        raise HTTPException(400, "Email уже зарегистрирован")
    teacher = Teacher(
        email=data.email,
        hashed_password=_hash(data.password),
        full_name=data.full_name,
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


@router.post("/login", response_model=LoginResponse,
             summary="Войти, получить JWT-токен")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db:   Session = Depends(get_db),
):
    teacher = db.query(Teacher).filter(Teacher.email == form.username).first()
    if not teacher or not _verify(form.password, teacher.hashed_password):
        raise HTTPException(401, "Неверный email или пароль")
    if not teacher.is_active:
        raise HTTPException(403, "Аккаунт деактивирован")
    return {"access_token": _make_token(str(teacher.id))}


@router.get("/me", response_model=TeacherOut, summary="Профиль текущего преподавателя")
def me(teacher: Teacher = Depends(get_current_teacher)):
    return teacher


@router.patch("/me", response_model=TeacherOut, summary="Обновить профиль")
def update_me(
    data:    ProfileUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db:      Session = Depends(get_db),
):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(teacher, field, value)
    db.commit()
    db.refresh(teacher)
    return teacher
