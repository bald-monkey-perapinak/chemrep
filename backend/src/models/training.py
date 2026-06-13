"""
Модель обучающего видео.
Видео загружаются преподавателем для дообучения бота его манере ведения урока.
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from src.db.base import Base


class VideoStatus(str, enum.Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"      # извлечение аудио + транскрибация
    ANALYZING = "analyzing"        # анализ стиля преподавания
    READY = "ready"                # профиль готов
    FAILED = "failed"


class TrainingVideo(Base):
    """
    Обучающее видео преподавателя.
    После обработки извлекается профиль стиля преподавания.
    """
    __tablename__ = "training_videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)

    # Метаданные файла
    original_name = Column(String(500), nullable=False)
    storage_path = Column(String(1000), nullable=False)  # путь в S3
    mime_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    duration_sec = Column(Float, nullable=True)           # длительность видео

    # Статус обработки
    status = Column(String(20), default=VideoStatus.UPLOADING)
    error_message = Column(Text, nullable=True)

    # Результаты обработки
    audio_path = Column(String(1000), nullable=True)      # путь к извлечённому аудио в S3
    transcript = Column(Text, nullable=True)               # полная транскрипция

    # Профиль стиля преподавания (JSONB)
    teaching_profile = Column(JSONB, nullable=True)
    # Пример структуры:
    # {
    #   "speech_pace": "normal",           # fast / normal / slow
    #   "avg_pause_sec": 1.2,              # средняя пауза между фразами
    #   "avg_sentence_words": 12,          # средняя длина предложения
    #   "question_frequency": 0.3,         # как часто задаёт вопросы
    #   "analogy_style": "everyday",       # everyday / academic / humorous
    #   "emotion_expressiveness": 0.7,     # 0-1, эмоциональность
    #   "structure_pattern": "explain_ask", # explain_ask / ask_explain / socratic
    #   "vocabulary_level": "school",      # school / university / mixed
    #   "filler_words": ["ну", "значит"],  # типичные слова-паразиты
    #   "key_phrases": ["давай разберём", "обрати внимание"],  # фирменные фразы
    #   "correction_style": "gentle",      # gentle / direct / socratic
    #   "opening_pattern": "greet_topic",  # greet_topic / review / question
    #   "closing_pattern": "summary_hw",   # summary_hw / recap / encourage
    # }

    # Прогресс обработки (0-100)
    progress = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    teacher = relationship("Teacher")

    def __repr__(self):
        return f"<TrainingVideo {self.original_name} status={self.status}>"


class TeachingProfile(Base):
    """
    Сводный профиль стиля преподавателя.
    Агрегируется из всех обработанных видео.
    """
    __tablename__ = "teaching_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id", ondelete="CASCADE"),
                        nullable=False, unique=True)

    # Агрегированный профиль
    profile = Column(JSONB, default=dict)
    # Пример:
    # {
    #   "speech_pace": "normal",
    #   "avg_pause_sec": 1.4,
    #   "avg_sentence_words": 11,
    #   "question_frequency": 0.35,
    #   "analogy_style": "everyday",
    #   "emotion_expressiveness": 0.65,
    #   "structure_pattern": "explain_ask",
    #   "vocabulary_level": "school",
    #   "filler_words": ["ну", "значит", "короче"],
    #   "key_phrases": ["давай разберём", "обрати внимание", "это важно"],
    #   "correction_style": "gentle",
    #   "opening_pattern": "greet_topic",
    #   "closing_pattern": "summary_hw",
    #   "videos_analyzed": 3,
    #   "total_duration_min": 120,
    # }

    # Количество видео для агрегации
    videos_count = Column(Integer, default=0)
    total_duration_min = Column(Float, default=0.0)

    # Системный промпт, сгенерированный на основе профиля
    custom_prompt = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    teacher = relationship("Teacher")

    def __repr__(self):
        return f"<TeachingProfile teacher={self.teacher_id}>"
