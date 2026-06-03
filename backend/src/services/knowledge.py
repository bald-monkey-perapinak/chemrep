"""
Сервисный слой для базы знаний.
Содержит всю бизнес-логику: CRUD для классов, секций, тем и файлов.
Роутеры вызывают только методы этого сервиса — не работают с моделями напрямую.
"""

from __future__ import annotations

import mimetypes
import os
import uuid
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session, selectinload

from src.models.knowledge import KnowledgeClass, KnowledgeSection, KnowledgeTopic, TopicFile
from src.api.schemas.knowledge import (
    ClassCreate, ClassUpdate,
    SectionCreate, SectionUpdate,
    TopicCreate, TopicUpdate,
)


# ─── Вспомогательные функции ───────────────────────────────────────────────

def _get_class_or_404(db: Session, class_id: UUID, teacher_id: UUID) -> KnowledgeClass:
    obj = db.query(KnowledgeClass).filter(
        KnowledgeClass.id == class_id,
        KnowledgeClass.teacher_id == teacher_id,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Класс не найден")
    return obj


def _get_section_or_404(db: Session, section_id: UUID, teacher_id: UUID) -> KnowledgeSection:
    obj = (
        db.query(KnowledgeSection)
        .join(KnowledgeClass, KnowledgeSection.class_id == KnowledgeClass.id)
        .filter(
            KnowledgeSection.id == section_id,
            KnowledgeClass.teacher_id == teacher_id,
        )
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Раздел не найден")
    return obj


def _get_topic_or_404(db: Session, topic_id: UUID, teacher_id: UUID) -> KnowledgeTopic:
    obj = (
        db.query(KnowledgeTopic)
        .join(KnowledgeSection, KnowledgeTopic.section_id == KnowledgeSection.id)
        .join(KnowledgeClass, KnowledgeSection.class_id == KnowledgeClass.id)
        .filter(
            KnowledgeTopic.id == topic_id,
            KnowledgeClass.teacher_id == teacher_id,
        )
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Тема не найдена")
    return obj


def _get_file_or_404(db: Session, file_id: UUID, teacher_id: UUID) -> TopicFile:
    obj = (
        db.query(TopicFile)
        .join(KnowledgeTopic, TopicFile.topic_id == KnowledgeTopic.id)
        .join(KnowledgeSection, KnowledgeTopic.section_id == KnowledgeSection.id)
        .join(KnowledgeClass, KnowledgeSection.class_id == KnowledgeClass.id)
        .filter(
            TopicFile.id == file_id,
            KnowledgeClass.teacher_id == teacher_id,
        )
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Файл не найден")
    return obj


# ═══════════════════════════════════════════════════════════════════════════
#  KnowledgeClass
# ═══════════════════════════════════════════════════════════════════════════

def list_classes(db: Session, teacher_id: UUID) -> list[KnowledgeClass]:
    return (
        db.query(KnowledgeClass)
        .options(selectinload(KnowledgeClass.sections))
        .filter(KnowledgeClass.teacher_id == teacher_id)
        .order_by(KnowledgeClass.sort_order, KnowledgeClass.created_at)
        .all()
    )


def get_class_tree(db: Session, class_id: UUID, teacher_id: UUID) -> KnowledgeClass:
    """Класс с полным деревом: секции → темы."""
    obj = (
        db.query(KnowledgeClass)
        .options(
            selectinload(KnowledgeClass.sections)
            .selectinload(KnowledgeSection.topics)
        )
        .filter(
            KnowledgeClass.id == class_id,
            KnowledgeClass.teacher_id == teacher_id,
        )
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Класс не найден")
    return obj


def create_class(db: Session, teacher_id: UUID, data: ClassCreate) -> KnowledgeClass:
    obj = KnowledgeClass(teacher_id=teacher_id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_class(db: Session, class_id: UUID, teacher_id: UUID, data: ClassUpdate) -> KnowledgeClass:
    obj = _get_class_or_404(db, class_id, teacher_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete_class(db: Session, class_id: UUID, teacher_id: UUID) -> None:
    obj = _get_class_or_404(db, class_id, teacher_id)
    db.delete(obj)
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  KnowledgeSection
# ═══════════════════════════════════════════════════════════════════════════

def list_sections(db: Session, class_id: UUID, teacher_id: UUID) -> list[KnowledgeSection]:
    _get_class_or_404(db, class_id, teacher_id)
    return (
        db.query(KnowledgeSection)
        .options(selectinload(KnowledgeSection.topics))
        .filter(KnowledgeSection.class_id == class_id)
        .order_by(KnowledgeSection.sort_order, KnowledgeSection.created_at)
        .all()
    )


def create_section(db: Session, class_id: UUID, teacher_id: UUID, data: SectionCreate) -> KnowledgeSection:
    _get_class_or_404(db, class_id, teacher_id)
    obj = KnowledgeSection(class_id=class_id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_section(db: Session, section_id: UUID, teacher_id: UUID, data: SectionUpdate) -> KnowledgeSection:
    obj = _get_section_or_404(db, section_id, teacher_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete_section(db: Session, section_id: UUID, teacher_id: UUID) -> None:
    obj = _get_section_or_404(db, section_id, teacher_id)
    db.delete(obj)
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  KnowledgeTopic
# ═══════════════════════════════════════════════════════════════════════════

def list_topics(db: Session, section_id: UUID, teacher_id: UUID) -> list[KnowledgeTopic]:
    _get_section_or_404(db, section_id, teacher_id)
    return (
        db.query(KnowledgeTopic)
        .options(selectinload(KnowledgeTopic.files))
        .filter(KnowledgeTopic.section_id == section_id)
        .order_by(KnowledgeTopic.sort_order, KnowledgeTopic.created_at)
        .all()
    )


def get_topic(db: Session, topic_id: UUID, teacher_id: UUID) -> KnowledgeTopic:
    obj = _get_topic_or_404(db, topic_id, teacher_id)
    # подгружаем файлы
    db.refresh(obj)
    return obj


def create_topic(db: Session, section_id: UUID, teacher_id: UUID, data: TopicCreate) -> KnowledgeTopic:
    _get_section_or_404(db, section_id, teacher_id)
    obj = KnowledgeTopic(section_id=section_id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_topic(db: Session, topic_id: UUID, teacher_id: UUID, data: TopicUpdate) -> KnowledgeTopic:
    obj = _get_topic_or_404(db, topic_id, teacher_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete_topic(db: Session, topic_id: UUID, teacher_id: UUID) -> None:
    obj = _get_topic_or_404(db, topic_id, teacher_id)
    db.delete(obj)
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  TopicFile
# ═══════════════════════════════════════════════════════════════════════════

# Разрешённые MIME-типы
ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",        # xlsx
    "application/msword",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "text/plain",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 МБ


async def upload_files(
    db: Session,
    topic_id: UUID,
    teacher_id: UUID,
    files: list[UploadFile],
    file_role: str = "material",
) -> tuple[list[TopicFile], list[str]]:
    """
    Загружает файлы в тему. Возвращает (загруженные, пропущенные).
    В реальном проекте здесь будет загрузка в S3.
    Пока сохраняем метаданные, путь эмулируем.
    """
    topic = _get_topic_or_404(db, topic_id, teacher_id)

    existing_names = {f.original_name for f in topic.files}
    uploaded: list[TopicFile] = []
    skipped: list[str] = []

    for upload in files:
        # Дубликат по имени — пропускаем
        if upload.filename in existing_names:
            skipped.append(upload.filename)
            continue

        content = await upload.read()
        size = len(content)

        if size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Файл «{upload.filename}» превышает 50 МБ",
            )

        mime = upload.content_type or mimetypes.guess_type(upload.filename or "")[0] or "application/octet-stream"
        if mime not in ALLOWED_MIME:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Тип файла не поддерживается: {mime}",
            )

        # Эмулируем путь в S3 (заменить на реальную загрузку)
        file_uuid = uuid.uuid4()
        ext = os.path.splitext(upload.filename or "")[1]
        storage_path = f"s3://chemrep/topics/{topic_id}/{file_uuid}{ext}"

        db_file = TopicFile(
            topic_id=topic_id,
            original_name=upload.filename,
            storage_path=storage_path,
            mime_type=mime,
            size_bytes=size,
            file_role=file_role,
        )
        db.add(db_file)
        uploaded.append(db_file)
        existing_names.add(upload.filename)

    db.commit()
    for f in uploaded:
        db.refresh(f)

    return uploaded, skipped


def delete_file(db: Session, file_id: UUID, teacher_id: UUID) -> None:
    obj = _get_file_or_404(db, file_id, teacher_id)
    # В реальном проекте: удалить из S3 по obj.storage_path
    db.delete(obj)
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  Поиск по базе знаний
# ═══════════════════════════════════════════════════════════════════════════

def search_topics(db: Session, teacher_id: UUID, q: str, limit: int = 20) -> list[KnowledgeTopic]:
    """Простой полнотекстовый поиск по названию и ключевым словам темы."""
    q = q.strip()
    if not q:
        return []
    pattern = f"%{q}%"
    return (
        db.query(KnowledgeTopic)
        .join(KnowledgeSection, KnowledgeTopic.section_id == KnowledgeSection.id)
        .join(KnowledgeClass, KnowledgeSection.class_id == KnowledgeClass.id)
        .filter(
            KnowledgeClass.teacher_id == teacher_id,
            KnowledgeTopic.is_published == True,  # noqa: E712
        )
        .filter(
            KnowledgeTopic.name.ilike(pattern)
            | KnowledgeTopic.keywords.ilike(pattern)
            | KnowledgeTopic.description.ilike(pattern)
        )
        .options(selectinload(KnowledgeTopic.files))
        .order_by(KnowledgeTopic.sort_order)
        .limit(limit)
        .all()
    )
