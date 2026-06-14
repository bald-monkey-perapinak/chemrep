"""
Сервисный слой для базы знаний.
Содержит всю бизнес-логику: CRUD для классов, секций, тем и файлов.
Роутеры вызывают только методы этого сервиса — не работают с моделями напрямую.
"""

from __future__ import annotations

import logging
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
from src.utils.text_extractor import extract_text
from src.utils.s3 import upload_bytes, delete_object, S3_BUCKET

logger = logging.getLogger(__name__)


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


def get_full_tree(db: Session, teacher_id: UUID) -> list[KnowledgeClass]:
    """Все классы с полным деревом: секции → темы. Один запрос вместо N+1."""
    return (
        db.query(KnowledgeClass)
        .options(
            selectinload(KnowledgeClass.sections)
            .selectinload(KnowledgeSection.topics)
        )
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
    Загружает файлы в тему: реальная загрузка в S3 + извлечение текста.
    Возвращает (загруженные, пропущенные).
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

        # Validate magic bytes to prevent MIME spoofing
        from src.utils.file_validator import validate_file_magic
        if not validate_file_magic(content[:32], mime):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Содержимое файла не соответствует типу {mime}",
            )

        # Генерируем путь в S3
        file_uuid = uuid.uuid4()
        ext = os.path.splitext(upload.filename or "")[1]
        storage_path = f"topics/{topic_id}/{file_uuid}{ext}"

        # Реальная загрузка в S3
        try:
            upload_bytes(content, storage_path, content_type=mime)
        except Exception as e:
            logger.error("[Knowledge] Ошибка загрузки в S3: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка загрузки файла в хранилище",
            )

        # Извлечение текста для RAG
        extracted_text = None
        text_extracted = False
        try:
            extracted_text = extract_text(content, upload.filename or "")
            text_extracted = extracted_text is not None
            if text_extracted:
                logger.info("[Knowledge] Извлечён текст из %s (%d символов)", upload.filename, len(extracted_text))
        except Exception as e:
            logger.warning("[Knowledge] Не удалось извлечь текст из %s: %s", upload.filename, e)

        db_file = TopicFile(
            topic_id=topic_id,
            original_name=upload.filename,
            storage_path=storage_path,
            mime_type=mime,
            size_bytes=size,
            file_role=file_role,
            extracted_text=extracted_text,
            text_extracted=text_extracted,
        )
        db.add(db_file)
        uploaded.append(db_file)
        existing_names.add(upload.filename)

        # Индексация эмбеддингов для RAG
        if text_extracted and extracted_text:
            try:
                from src.services.embeddings import index_topic_file
                index_topic_file(db, db_file, extracted_text, teacher_id)
            except Exception as e:
                logger.warning("[Knowledge] Не удалось проиндексировать эмбеддинги: %s", e)

    db.commit()
    for f in uploaded:
        db.refresh(f)

    return uploaded, skipped


def delete_file(db: Session, file_id: UUID, teacher_id: UUID) -> None:
    obj = _get_file_or_404(db, file_id, teacher_id)
    # Удаляем из S3
    try:
        delete_object(obj.storage_path)
    except Exception as e:
        logger.warning("[Knowledge] Не удалось удалить файл из S3: %s", e)
    # Удаляем эмбеддинги
    try:
        from src.services.embeddings import delete_embeddings_for_source
        delete_embeddings_for_source(db, "topic_file", file_id)
    except Exception:
        pass
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
    # Экранируем спецсимволы SQL LIKE
    safe = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{safe}%"
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
