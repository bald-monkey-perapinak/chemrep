"""
Pydantic-схемы для knowledge API.
Разделены на *Create*, *Update* и *Read* (с id, датами и вложенными объектами).
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ── Вспомогательный миксин ─────────────────────────────────────────────────

class OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════════════════
#  TopicFile
# ═══════════════════════════════════════════════════════════════════════════

class TopicFileRead(OrmBase):
    id: UUID
    topic_id: UUID
    original_name: str
    storage_path: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    file_role: str
    text_extracted: bool
    uploaded_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
#  KnowledgeTopic
# ═══════════════════════════════════════════════════════════════════════════

class TopicCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    keywords: Optional[str] = None
    lesson_script: Optional[list[dict[str, Any]]] = None
    miro_board_id: Optional[str] = None
    miro_board_url: Optional[str] = None
    estimated_duration_min: int = 45
    sort_order: int = 0
    is_published: bool = True


class TopicUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    keywords: Optional[str] = None
    lesson_script: Optional[list[dict[str, Any]]] = None
    miro_board_id: Optional[str] = None
    miro_board_url: Optional[str] = None
    estimated_duration_min: Optional[int] = None
    sort_order: Optional[int] = None
    is_published: Optional[bool] = None


class TopicRead(OrmBase):
    id: UUID
    section_id: UUID
    name: str
    description: Optional[str] = None
    keywords: Optional[str] = None
    lesson_script: Optional[list[dict[str, Any]]] = None
    miro_board_id: Optional[str] = None
    miro_board_url: Optional[str] = None
    estimated_duration_min: int
    sort_order: int
    is_published: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    files: list[TopicFileRead] = []


class TopicShort(OrmBase):
    """Краткое представление темы — для вложения в Section без файлов."""
    id: UUID
    name: str
    description: Optional[str] = None
    estimated_duration_min: int
    sort_order: int
    is_published: bool
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
#  KnowledgeSection
# ═══════════════════════════════════════════════════════════════════════════

class SectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    sort_order: int = 0


class SectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    sort_order: Optional[int] = None


class SectionRead(OrmBase):
    id: UUID
    class_id: UUID
    name: str
    description: Optional[str] = None
    sort_order: int
    created_at: datetime
    topics: list[TopicShort] = []


class SectionShort(OrmBase):
    id: UUID
    name: str
    description: Optional[str] = None
    sort_order: int
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
#  KnowledgeClass
# ═══════════════════════════════════════════════════════════════════════════

class ClassCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    grade_number: Optional[int] = None
    sort_order: int = 0


class ClassUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    grade_number: Optional[int] = None
    sort_order: Optional[int] = None


class ClassRead(OrmBase):
    id: UUID
    teacher_id: UUID
    name: str
    grade_number: Optional[int] = None
    sort_order: int
    created_at: datetime
    sections: list[SectionShort] = []


class ClassReadFull(OrmBase):
    """Класс с вложенными секциями и темами — для дерева."""
    id: UUID
    teacher_id: UUID
    name: str
    grade_number: Optional[int] = None
    sort_order: int
    created_at: datetime
    sections: list[SectionRead] = []


# ═══════════════════════════════════════════════════════════════════════════
#  File upload response
# ═══════════════════════════════════════════════════════════════════════════

class FileUploadResponse(BaseModel):
    uploaded: list[TopicFileRead]
    skipped: list[str] = []   # имена файлов, которые уже есть в теме
