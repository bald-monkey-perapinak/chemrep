"""
Extract API — извлечение текста из файлов (PDF, DOCX) для импорта сценариев.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel

from src.utils.text_extractor import extract_text
from src.api.routes.auth import get_current_teacher

router = APIRouter(prefix="/extract", tags=["extract"])


class ExtractResponse(BaseModel):
    text: str
    filename: str
    length: int


@router.post(
    "/text",
    response_model=ExtractResponse,
    summary="Извлечь текст из файла",
    description="Принимает PDF, DOCX или TXT файл и возвращает извлечённый текст.",
)
async def extract_file_text(
    file: UploadFile = File(...),
    current_user=Depends(get_current_teacher),
):
    filename = file.filename or "unknown"

    if not filename:
        raise HTTPException(400, "Имя файла обязательно")

    content = await file.read()

    if len(content) > 10 * 1024 * 1024:  # 10 MB
        raise HTTPException(413, "Файл слишком большой (максимум 10 МБ)")

    text = extract_text(content, filename)

    if text is None:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"
        raise HTTPException(
            422,
            f"Не удалось извлечь текст из файла .{ext}. "
            "Поддерживаемые форматы: PDF, DOCX, TXT",
        )

    return ExtractResponse(
        text=text,
        filename=filename,
        length=len(text),
    )
