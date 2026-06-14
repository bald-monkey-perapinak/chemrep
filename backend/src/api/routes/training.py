"""
Training API — загрузка и анализ обучающих видео.

POST   /api/training/videos           — загрузить видео
GET    /api/training/videos           — список видео
GET    /api/training/videos/{id}      — детали видео
DELETE /api/training/videos/{id}      — удалить видео
POST   /api/training/videos/{id}/process — запустить обработку
GET    /api/training/profile          — профиль стиля преподавания
"""

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.db.base import get_db
from src.api.routes.auth import get_current_teacher
from src.models.teacher import Teacher
from src.models.training import TrainingVideo, TeachingProfile, VideoStatus
from src.utils.s3 import upload_bytes

router = APIRouter(prefix="/training", tags=["training"])

MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500 МБ
ALLOWED_VIDEO = {
    "video/mp4", "video/webm", "video/quicktime", "video/x-msvideo",
    "video/x-matroska",
}

# Dedup: track currently processing video IDs to prevent double launches
_processing_videos: set[uuid.UUID] = set()


# ── Схемы ───────────────────────────────────────────────────────────────────

class VideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_name: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    duration_sec: Optional[float] = None
    status: str
    progress: int = 0
    error_message: Optional[str] = None
    transcript: Optional[str] = None
    teaching_profile: Optional[dict] = None
    created_at: Optional[str] = None


class VideoUploadResult(BaseModel):
    id: uuid.UUID
    filename: str
    message: str


class TeachingProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile: dict = {}
    videos_count: int = 0
    total_duration_min: float = 0.0
    custom_prompt: Optional[str] = None


# ── Эндпоинты ─────────────────────────────────────────────────────────────

@router.post(
    "/videos",
    response_model=VideoUploadResult,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить обучающее видео",
)
async def upload_video(
    file: UploadFile = File(..., description="Видео (MP4/WebM, до 500 МБ)"),
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    mime = file.content_type or ""
    if not mime.startswith("video/"):
        raise HTTPException(415, f"Неподдерживаемый тип: {file.filename}. Допустимы только видеофайлы.")

    content = await file.read()
    if len(content) > MAX_VIDEO_SIZE:
        raise HTTPException(413, f"Файл больше 500 МБ")

    # Сохраняем в S3
    video_id = uuid.uuid4()
    ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    storage_path = f"training/{teacher.id}/{video_id}{ext}"
    upload_bytes(content, storage_path, content_type=mime)

    # Создаём запись в БД
    video = TrainingVideo(
        id=video_id,
        teacher_id=teacher.id,
        original_name=file.filename or "video.mp4",
        storage_path=storage_path,
        mime_type=mime,
        size_bytes=len(content),
        status=VideoStatus.UPLOADING,
    )
    db.add(video)
    db.commit()

    return VideoUploadResult(
        id=video_id,
        filename=file.filename or "video.mp4",
        message="Видео загружено. Нажмите «Обработать» для анализа.",
    )


@router.get(
    "/videos",
    response_model=list[VideoRead],
    summary="Список обучающих видео",
)
def list_videos(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    videos = (
        db.query(TrainingVideo)
        .filter(TrainingVideo.teacher_id == teacher.id)
        .order_by(TrainingVideo.created_at.desc())
        .all()
    )
    result = []
    for v in videos:
        result.append(VideoRead(
            id=v.id,
            original_name=v.original_name,
            mime_type=v.mime_type,
            size_bytes=v.size_bytes,
            duration_sec=v.duration_sec,
            status=v.status,
            progress=v.progress,
            error_message=v.error_message,
            transcript=v.transcript,
            teaching_profile=v.teaching_profile,
            created_at=v.created_at.isoformat() if v.created_at else None,
        ))
    return result


@router.get(
    "/videos/{video_id}",
    response_model=VideoRead,
    summary="Детали видео",
)
def get_video(
    video_id: uuid.UUID,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    video = db.query(TrainingVideo).filter(
        TrainingVideo.id == video_id,
        TrainingVideo.teacher_id == teacher.id,
    ).first()
    if not video:
        raise HTTPException(404, "Видео не найдено")
    return VideoRead(
        id=video.id,
        original_name=video.original_name,
        mime_type=video.mime_type,
        size_bytes=video.size_bytes,
        duration_sec=video.duration_sec,
        status=video.status,
        progress=video.progress,
        error_message=video.error_message,
        transcript=video.transcript,
        teaching_profile=video.teaching_profile,
        created_at=video.created_at.isoformat() if video.created_at else None,
    )


@router.delete(
    "/videos/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить видео",
)
def delete_video(
    video_id: uuid.UUID,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    video = db.query(TrainingVideo).filter(
        TrainingVideo.id == video_id,
        TrainingVideo.teacher_id == teacher.id,
    ).first()
    if not video:
        raise HTTPException(404, "Видео не найдено")

    # Удаляем из S3
    try:
        from src.utils.s3 import delete_object
        delete_object(video.storage_path)
        if video.audio_path:
            delete_object(video.audio_path)
    except Exception:
        pass

    db.delete(video)
    db.commit()


@router.post(
    "/videos/{video_id}/process",
    summary="Запустить обработку видео",
    description="Извлекает аудио, транскрибирует и анализирует стиль преподавания.",
)
async def process_video(
    video_id: uuid.UUID,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    video = db.query(TrainingVideo).filter(
        TrainingVideo.id == video_id,
        TrainingVideo.teacher_id == teacher.id,
    ).first()
    if not video:
        raise HTTPException(404, "Видео не найдено")

    if video.status in (VideoStatus.PROCESSING, VideoStatus.ANALYZING):
        raise HTTPException(409, "Видео уже обрабатывается")

    if video.id in _processing_videos:
        raise HTTPException(409, "Видео уже обрабатывается")

    _processing_videos.add(video.id)

    # Запускаем обработку в фоне
    import asyncio
    asyncio.create_task(_process_video(video.id, db))

    return {"message": "Обработка запущена", "video_id": str(video_id)}


async def _process_video(video_id: uuid.UUID, db: Session):
    """Фоновая обработка видео: аудио → транскрипция → анализ стиля."""
    from src.models.training import TrainingVideo, VideoStatus

    video = db.query(TrainingVideo).filter(TrainingVideo.id == video_id).first()
    if not video:
        return

    try:
        # Шаг 1: Извлечение аудио
        video.status = VideoStatus.PROCESSING
        video.progress = 10
        db.commit()

        audio_path = await _extract_audio(video)
        video.audio_path = audio_path
        video.progress = 30
        db.commit()

        # Шаг 2: Транскрибация
        video.progress = 40
        db.commit()

        transcript = await _transcribe_audio(audio_path)
        video.transcript = transcript
        video.progress = 70
        db.commit()

        # Шаг 3: Анализ стиля
        video.status = VideoStatus.ANALYZING
        video.progress = 80
        db.commit()

        profile = await _analyze_teaching_style(transcript, video)
        video.teaching_profile = profile
        video.progress = 95
        db.commit()

        # Шаг 4: Обновляем сводный профиль
        await _update_teaching_profile(video.teacher_id, db)

        video.status = VideoStatus.READY
        video.progress = 100
        db.commit()

    except Exception as e:
        video.status = VideoStatus.FAILED
        video.error_message = str(e)[:500]
        db.commit()
    finally:
        _processing_videos.discard(video_id)


async def _extract_audio(video: TrainingVideo) -> str:
    """Извлечь аудио из видео через ffmpeg."""
    import subprocess
    import tempfile

    # Скачиваем видео во временную директорию
    from src.utils.s3 import download_bytes
    video_data = download_bytes(video.storage_path)

    with tempfile.TemporaryDirectory() as tmp:
        video_path = os.path.join(tmp, "input.mp4")
        audio_path = os.path.join(tmp, "audio.wav")

        with open(video_path, "wb") as f:
            f.write(video_data)

        # Извлекаем аудио
        result = subprocess.run(
            [
                "ffmpeg", "-i", video_path,
                "-vn",                     # без видео
                "-acodec", "pcm_s16le",    # 16-bit PCM
                "-ar", "16000",            # 16 kHz
                "-ac", "1",                # моно
                audio_path,
            ],
            capture_output=True,
            timeout=300,
        )

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg error: {result.stderr.decode()[:200]}")

        # Получаем длительность
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, timeout=30,
        )
        if probe.returncode == 0 and probe.stdout.strip():
            video.duration_sec = float(probe.stdout.strip())

        # Загружаем аудио в S3
        with open(audio_path, "rb") as f:
            audio_data = f.read()

        audio_s3_path = f"training/{video.teacher_id}/{video.id}/audio.wav"
        upload_bytes(audio_data, audio_s3_path, content_type="audio/wav")

        return audio_s3_path


async def _transcribe_audio(audio_path: str) -> str:
    """Транскрибировать аудио через Whisper API (или локальный Whisper)."""
    from src.utils.s3 import download_bytes

    audio_data = download_bytes(audio_path)

    # Пытаемся использовать OpenAI Whisper API
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        import httpx
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {openai_key}"},
                files={"file": ("audio.wav", audio_data, "audio/wav")},
                data={"model": "whisper-1", "language": "ru"},
            )
            if resp.status_code == 200:
                return resp.json().get("text", "")

    # Fallback: локальный faster-whisper
    try:
        from faster_whisper import WhisperModel
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            tmp_path = f.name

        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, info = model.transcribe(tmp_path, language="ru")
        text = " ".join(seg.text for seg in segments)

        os.unlink(tmp_path)
        return text

    except ImportError:
        raise RuntimeError("Нет доступного Whisper. Установите OPENAI_API_KEY или faster-whisper.")


async def _analyze_teaching_style(transcript: str, video: TrainingVideo) -> dict:
    """Анализировать стиль преподавания через LLM."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _analyze_transcript_heuristic(transcript, video)

    import httpx

    prompt = f"""Ты — эксперт по педагогике. Проанализируй транскрипцию урока и определи стиль преподавания.

Транскрипция (первые 3000 символов):
{transcript[:3000]}

Определи следующие параметры (только JSON, без markdown):
{{
  "speech_pace": "fast/normal/slow",
  "avg_sentence_words": число слов в среднем предложении,
  "question_frequency": доля предложений-вопросов (0.0-1.0),
  "analogy_style": "everyday/academic/humorous",
  "emotion_expressiveness": 0.0-1.0,
  "structure_pattern": "explain_ask/ask_explain/socratic",
  "vocabulary_level": "school/university/mixed",
  "filler_words": ["список слов-паразитов из транскрипции"],
  "key_phrases": ["3-5 фирменных фраз преподавателя"],
  "correction_style": "gentle/direct/socratic",
  "opening_pattern": "greet_topic/review/question",
  "closing_pattern": "summary_hw/recap/encourage",
  "emotional_markers": ["список эмоциональных маркеров"],
  "humor_frequency": "rare/occasional/frequent"
}}"""

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        data = resp.json()

        text = data["content"][0]["text"].strip()
        # Парсим JSON
        import re, json
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
        return json.loads(text)


def _analyze_transcript_heuristic(transcript: str, video: TrainingVideo) -> dict:
    """Простой эвристический анализ без LLM."""
    import re

    sentences = re.split(r'[.!?]+', transcript)
    sentences = [s.strip() for s in sentences if s.strip()]

    questions = sum(1 for s in sentences if s.endswith('?'))
    words = transcript.split()
    avg_words = len(words) / max(1, len(sentences))

    # Ищем слова-паразиты
    filler_candidates = ["ну", "значит", "короче", "то есть", "вот", "как бы", "ээ"]
    fillers = [f for f in filler_candidates if transcript.lower().count(f) > 3]

    return {
        "speech_pace": "normal",
        "avg_sentence_words": round(avg_words, 1),
        "question_frequency": round(questions / max(1, len(sentences)), 2),
        "analogy_style": "everyday",
        "emotion_expressiveness": 0.5,
        "structure_pattern": "explain_ask",
        "vocabulary_level": "school",
        "filler_words": fillers,
        "key_phrases": [],
        "correction_style": "gentle",
        "opening_pattern": "greet_topic",
        "closing_pattern": "summary_hw",
        "emotional_markers": [],
        "humor_frequency": "occasional",
    }


async def _update_teaching_profile(teacher_id: uuid.UUID, db: Session):
    """Обновить сводный профиль преподавателя на основе всех видео."""
    videos = (
        db.query(TrainingVideo)
        .filter(
            TrainingVideo.teacher_id == teacher_id,
            TrainingVideo.status == VideoStatus.READY,
            TrainingVideo.teaching_profile.isnot(None),
        )
        .all()
    )

    if not videos:
        return

    # Агрегируем профили (средние значения)
    aggregated = {}
    numeric_fields = [
        "avg_sentence_words", "question_frequency",
        "emotion_expressiveness",
    ]

    for field in numeric_fields:
        values = [v.teaching_profile.get(field, 0) for v in videos if v.teaching_profile]
        if values:
            aggregated[field] = round(sum(values) / len(values), 2)

    # Берём наиболее частые значения для категориальных полей
    categorical_fields = [
        "speech_pace", "analogy_style", "structure_pattern",
        "vocabulary_level", "correction_style", "opening_pattern",
        "closing_pattern", "humor_frequency",
    ]
    for field in categorical_fields:
        values = [v.teaching_profile.get(field) for v in videos if v.teaching_profile and v.teaching_profile.get(field)]
        if values:
            from collections import Counter
            aggregated[field] = Counter(values).most_common(1)[0][0]

    # Объединяем списки
    list_fields = ["filler_words", "key_phrases", "emotional_markers"]
    for field in list_fields:
        all_items = []
        for v in videos:
            if v.teaching_profile:
                all_items.extend(v.teaching_profile.get(field, []))
        if all_items:
            from collections import Counter
            aggregated[field] = [item for item, _ in Counter(all_items).most_common(10)]

    aggregated["videos_analyzed"] = len(videos)
    aggregated["total_duration_min"] = round(
        sum(v.duration_sec or 0 for v in videos) / 60, 1
    )

    # Генерируем кастомный промпт
    custom_prompt = _generate_custom_prompt(aggregated)

    # Сохраняем/обновляем профиль
    profile = db.query(TeachingProfile).filter(
        TeachingProfile.teacher_id == teacher_id
    ).first()

    if not profile:
        profile = TeachingProfile(teacher_id=teacher_id)
        db.add(profile)

    profile.profile = aggregated
    profile.videos_count = len(videos)
    profile.total_duration_min = aggregated["total_duration_min"]
    profile.custom_prompt = custom_prompt

    db.commit()


def _generate_custom_prompt(profile: dict) -> str:
    """Сгенерировать кастомный промпт на основе профиля стиля."""
    parts = []

    pace = profile.get("speech_pace", "normal")
    pace_map = {
        "fast": "Говоришь较快, без длинных пауз",
        "normal": "Говоришь размеренно, с умеренными паузами",
        "slow": "Говоришь медленно, делая акцент на каждом слове",
    }
    parts.append(pace_map.get(pace, pace_map["normal"]))

    structure = profile.get("structure_pattern", "explain_ask")
    structure_map = {
        "explain_ask": "Сначала объясняешь, потом задаёшь вопрос для проверки",
        "ask_explain": "Сначала задаёшь вопрос, потом объясняешь",
        "socratic": "Используешь сократовский метод — подводишь к ответу через вопросы",
    }
    parts.append(structure_map.get(structure, structure_map["explain_ask"]))

    correction = profile.get("correction_style", "gentle")
    correction_map = {
        "gentle": "При ошибке мягко направляешь: «Почти! Давай разберёмся...»",
        "direct": "При ошибке сразу говоришь правильный ответ с объяснением",
        "socratic": "При ошибке задаёшь наводящие вопросы, чтобы ученик нашёл ошибку сам",
    }
    parts.append(correction_map.get(correction, correction_map["gentle"]))

    key_phrases = profile.get("key_phrases", [])
    if key_phrases:
        parts.append(f"Твои фирменные фразы: {', '.join(key_phrases[:5])}")

    filler_words = profile.get("filler_words", [])
    if filler_words:
        parts.append(f"Используй слова-паразиты для естественности: {', '.join(filler_words[:3])}")

    emotional = profile.get("emotional_markers", [])
    if emotional:
        parts.append(f"Эмоциональные маркер: {', '.join(emotional[:3])}")

    return "\n".join(parts)


@router.get(
    "/profile",
    response_model=TeachingProfileRead,
    summary="Профиль стиля преподавания",
)
def get_teaching_profile(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    profile = db.query(TeachingProfile).filter(
        TeachingProfile.teacher_id == teacher.id
    ).first()

    if not profile:
        return TeachingProfileRead(
            id=uuid.uuid4(),
            profile={},
            videos_count=0,
            total_duration_min=0.0,
            custom_prompt=None,
        )

    return TeachingProfileRead(
        id=profile.id,
        profile=profile.profile or {},
        videos_count=profile.videos_count,
        total_duration_min=profile.total_duration_min,
        custom_prompt=profile.custom_prompt,
    )
