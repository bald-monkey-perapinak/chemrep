"""
Knowledge API — роутер базы знаний.

Иерархия ресурсов:
  /knowledge/classes                          — классы (8, 9, 10, 11 класс)
  /knowledge/classes/{class_id}/sections      — разделы внутри класса
  /knowledge/sections/{section_id}/topics     — темы внутри раздела
  /knowledge/topics/{topic_id}/files          — файлы темы
  /knowledge/files/{file_id}                  — операции с конкретным файлом
  /knowledge/search                           — поиск по темам

Все эндпоинты требуют идентификации преподавателя (X-Teacher-Id или фоллбэк на первого в БД).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile, File, status
from sqlalchemy.orm import Session

from src.db.base import get_db
from src.api.deps import get_current_teacher
from src.models.teacher import Teacher
from src.services import knowledge as svc
from src.api.schemas.knowledge import (
    ClassCreate, ClassUpdate, ClassRead, ClassReadFull,
    SectionCreate, SectionUpdate, SectionRead,
    TopicCreate, TopicUpdate, TopicRead,
    TopicFileRead, FileUploadResponse,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# ═══════════════════════════════════════════════════════════════════════════
#  KnowledgeClass
# ═══════════════════════════════════════════════════════════════════════════

@router.get(
    "/classes",
    response_model=list[ClassRead],
    summary="Список классов",
    description="Возвращает все классы преподавателя с вложенными разделами (без тем).",
)
def list_classes(
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return svc.list_classes(db, teacher.id)


@router.get(
    "/classes/{class_id}/tree",
    response_model=ClassReadFull,
    summary="Полное дерево класса",
    description="Класс → разделы → темы. Файлы тем не включены.",
)
def get_class_tree(
    class_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return svc.get_class_tree(db, class_id, teacher.id)


@router.post(
    "/classes",
    response_model=ClassRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать класс",
)
def create_class(
    data: ClassCreate,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return svc.create_class(db, teacher.id, data)


@router.patch(
    "/classes/{class_id}",
    response_model=ClassRead,
    summary="Обновить класс",
)
def update_class(
    class_id: UUID,
    data: ClassUpdate,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return svc.update_class(db, class_id, teacher.id, data)


@router.delete(
    "/classes/{class_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить класс",
    description="Каскадно удаляет все разделы, темы и файлы внутри.",
)
def delete_class(
    class_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    svc.delete_class(db, class_id, teacher.id)


# ═══════════════════════════════════════════════════════════════════════════
#  KnowledgeSection
# ═══════════════════════════════════════════════════════════════════════════

@router.get(
    "/classes/{class_id}/sections",
    response_model=list[SectionRead],
    summary="Разделы класса",
)
def list_sections(
    class_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return svc.list_sections(db, class_id, teacher.id)


@router.post(
    "/classes/{class_id}/sections",
    response_model=SectionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать раздел",
)
def create_section(
    class_id: UUID,
    data: SectionCreate,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return svc.create_section(db, class_id, teacher.id, data)


@router.patch(
    "/sections/{section_id}",
    response_model=SectionRead,
    summary="Обновить раздел",
)
def update_section(
    section_id: UUID,
    data: SectionUpdate,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return svc.update_section(db, section_id, teacher.id, data)


@router.delete(
    "/sections/{section_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить раздел",
    description="Каскадно удаляет все темы и файлы внутри.",
)
def delete_section(
    section_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    svc.delete_section(db, section_id, teacher.id)


# ═══════════════════════════════════════════════════════════════════════════
#  KnowledgeTopic
# ═══════════════════════════════════════════════════════════════════════════

@router.get(
    "/sections/{section_id}/topics",
    response_model=list[TopicRead],
    summary="Темы раздела",
)
def list_topics(
    section_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return svc.list_topics(db, section_id, teacher.id)


@router.get(
    "/topics/{topic_id}",
    response_model=TopicRead,
    summary="Тема с файлами",
)
def get_topic(
    topic_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return svc.get_topic(db, topic_id, teacher.id)


@router.post(
    "/sections/{section_id}/topics",
    response_model=TopicRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать тему",
)
def create_topic(
    section_id: UUID,
    data: TopicCreate,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return svc.create_topic(db, section_id, teacher.id, data)


@router.patch(
    "/topics/{topic_id}",
    response_model=TopicRead,
    summary="Обновить тему",
    description="Частичное обновление: передавайте только изменяемые поля.",
)
def update_topic(
    topic_id: UUID,
    data: TopicUpdate,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return svc.update_topic(db, topic_id, teacher.id, data)


@router.delete(
    "/topics/{topic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить тему",
)
def delete_topic(
    topic_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    svc.delete_topic(db, topic_id, teacher.id)


# ═══════════════════════════════════════════════════════════════════════════
#  TopicFile
# ═══════════════════════════════════════════════════════════════════════════

@router.post(
    "/topics/{topic_id}/files",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить файлы в тему",
    description=(
        "Принимает один или несколько файлов (multipart/form-data). "
        "Допустимые типы: PDF, DOCX, XLSX, PNG, JPEG, GIF, WEBP, TXT. "
        "Максимальный размер: 50 МБ на файл. "
        "Дубликаты по имени пропускаются и возвращаются в поле `skipped`."
    ),
)
async def upload_files(
    topic_id: UUID,
    files: list[UploadFile] = File(..., description="Один или несколько файлов"),
    file_role: str = Query("material", description="material | homework | image | other"),
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    uploaded, skipped = await svc.upload_files(db, topic_id, teacher.id, files, file_role)
    return FileUploadResponse(uploaded=uploaded, skipped=skipped)


@router.delete(
    "/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить файл",
)
def delete_file(
    file_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    svc.delete_file(db, file_id, teacher.id)


# ═══════════════════════════════════════════════════════════════════════════
#  Поиск
# ═══════════════════════════════════════════════════════════════════════════

@router.get(
    "/search",
    response_model=list[TopicRead],
    summary="Поиск по базе знаний",
    description="Ищет темы по названию, описанию и ключевым словам. Минимум 2 символа.",
)
def search(
    q: str = Query(..., min_length=2, description="Поисковый запрос"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    return svc.search_topics(db, teacher.id, q, limit)


# ═══════════════════════════════════════════════════════════════════════════
#  Topic Assets (SVG, images for the whiteboard)
# ═══════════════════════════════════════════════════════════════════════════

@router.get(
    "/topics/{topic_id}/assets",
    summary="Список ассетов темы",
)
def list_assets(
    topic_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    from src.models.knowledge import TopicAsset
    return db.query(TopicAsset).filter(
        TopicAsset.topic_id == topic_id,
    ).order_by(TopicAsset.uploaded_at).all()


@router.post(
    "/topics/{topic_id}/assets",
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить ассет (SVG, изображение)",
)
async def upload_asset(
    topic_id: UUID,
    file: UploadFile = File(...),
    asset_type: str = Query("svg", description="svg | image | other"),
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    import uuid as _uuid, os
    from src.models.knowledge import TopicAsset
    from src.utils.s3 import upload_bytes

    content = await file.read()
    ext = os.path.splitext(file.filename or "")[1]
    storage_path = f"topics/{topic_id}/assets/{_uuid.uuid4()}{ext}"

    upload_bytes(content, storage_path, content_type=file.content_type or "image/svg+xml")

    asset = TopicAsset(
        topic_id=topic_id,
        original_name=file.filename or "unnamed",
        storage_path=storage_path,
        mime_type=file.content_type,
        asset_type=asset_type,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.delete(
    "/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить ассет",
)
def delete_asset(
    asset_id: UUID,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    from src.models.knowledge import TopicAsset
    from src.utils.s3 import delete_object

    asset = db.query(TopicAsset).filter(TopicAsset.id == asset_id).first()
    if not asset:
        from fastapi import HTTPException
        raise HTTPException(404, "Ассет не найден")

    try:
        delete_object(asset.storage_path)
    except Exception:
        pass

    db.delete(asset)
    db.commit()
