"""
Voice API — клонирование голоса преподавателя через ElevenLabs.

POST /api/voice/clone     — загрузить образцы голоса, создать клон в ElevenLabs
GET  /api/voice/status    — статус клонирования
DELETE /api/voice         — удалить клонированный голос
"""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

import httpx

from src.db.base import get_db
from src.api.routes.auth import get_current_teacher
from src.models.teacher import Teacher

router = APIRouter(prefix="/voice", tags=["voice"])

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"
MAX_SAMPLE_SIZE = 10 * 1024 * 1024   # 10 МБ на файл
ALLOWED_AUDIO   = {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/m4a"}


class VoiceStatus(BaseModel):
    has_clone:    bool
    voice_id:     Optional[str]
    voice_name:   Optional[str]
    model_ready:  bool


class CloneResult(BaseModel):
    voice_id:  str
    voice_name: str
    message:   str


# ── Эндпоинты ─────────────────────────────────────────────────────────────

@router.get("/status", response_model=VoiceStatus,
            summary="Статус клонированного голоса")
def voice_status(
    teacher: Teacher = Depends(get_current_teacher),
):
    return VoiceStatus(
        has_clone=bool(teacher.voice_model_path),
        voice_id=teacher.voice_model_path,
        voice_name=f"Голос — {teacher.full_name}" if teacher.voice_model_path else None,
        model_ready=teacher.voice_model_ready,
    )


@router.post("/clone", response_model=CloneResult, status_code=201,
             summary="Загрузить образцы голоса и создать клон")
async def clone_voice(
    files:   list[UploadFile] = File(..., description="Аудиофайлы с образцами голоса (MP3/WAV, 1–25 файлов, от 1 минуты суммарно)"),
    teacher: Teacher          = Depends(get_current_teacher),
    db:      Session          = Depends(get_db),
):
    api_key = os.getenv("ELEVENLABS_API_KEY", "")
    if not api_key:
        raise HTTPException(503, "ELEVENLABS_API_KEY не настроен")

    if len(files) < 1 or len(files) > 25:
        raise HTTPException(400, "Нужно от 1 до 25 аудиофайлов")

    # Читаем файлы и валидируем
    samples = []
    for upload in files:
        mime = upload.content_type or ""
        if not any(a in mime for a in ("audio", "mpeg", "wav", "mp4")):
            raise HTTPException(415, f"Неподдерживаемый тип: {upload.filename}")
        content = await upload.read()
        if len(content) > MAX_SAMPLE_SIZE:
            raise HTTPException(413, f"Файл {upload.filename} больше 10 МБ")
        samples.append((upload.filename or "sample.mp3", content, mime or "audio/mpeg"))

    voice_name = f"Teacher_{teacher.id}"

    # Отправляем в ElevenLabs Add Voice API
    async with httpx.AsyncClient(timeout=60.0) as client:
        form_data = {"name": voice_name}
        files_data = [
            ("files", (name, data, mime))
            for name, data, mime in samples
        ]
        try:
            resp = await client.post(
                f"{ELEVENLABS_BASE}/voices/add",
                headers={"xi-api-key": api_key},
                data=form_data,
                files=files_data,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(502, f"ElevenLabs error: {e.response.text[:200]}")
        except Exception as e:
            raise HTTPException(502, f"Ошибка соединения с ElevenLabs: {e}")

        result = resp.json()
        voice_id = result.get("voice_id")
        if not voice_id:
            raise HTTPException(502, "ElevenLabs не вернул voice_id")

    # Сохраняем voice_id в профиле преподавателя
    teacher.voice_model_path  = voice_id
    teacher.voice_model_ready = True
    db.commit()

    return CloneResult(
        voice_id=voice_id,
        voice_name=voice_name,
        message="Голос успешно клонирован. Бот будет использовать его на следующих уроках.",
    )


@router.delete("", status_code=204,
               summary="Удалить клонированный голос")
async def delete_voice(
    teacher: Teacher = Depends(get_current_teacher),
    db:      Session = Depends(get_db),
):
    if not teacher.voice_model_path:
        raise HTTPException(404, "Клонированный голос не найден")

    api_key = os.getenv("ELEVENLABS_API_KEY", "")
    if api_key:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                await client.delete(
                    f"{ELEVENLABS_BASE}/voices/{teacher.voice_model_path}",
                    headers={"xi-api-key": api_key},
                )
            except Exception as e:
                # Не блокируем удаление из БД если ElevenLabs недоступен
                pass

    teacher.voice_model_path  = None
    teacher.voice_model_ready = False
    db.commit()
