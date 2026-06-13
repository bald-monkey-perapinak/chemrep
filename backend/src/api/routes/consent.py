"""
Consent API — управление согласием родителей на запись несовершеннолетних.

Эндпоинты:
  POST /consent          — создать/обновить согласие
  GET  /consent/{id}     — получить согласие
  GET  /consent/student/{student_id} — проверить согласие ученика
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from src.api.routes.auth import get_current_teacher
from src.db.base import get_db
from src.models.consent import ParentalConsent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/consent", tags=["consent"])


class ConsentCreate(BaseModel):
    student_id: UUID
    parent_email: EmailStr
    parent_name: str
    consent_given: bool = False
    recording_allowed: bool = False
    data_processing_allowed: bool = False


class ConsentResponse(BaseModel):
    id: UUID
    student_id: UUID
    parent_email: str
    parent_name: str
    consent_given: bool
    recording_allowed: bool
    data_processing_allowed: bool
    consent_date: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("", response_model=ConsentResponse)
async def create_or_update_consent(
    data: ConsentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_teacher),
):
    """Создать или обновить согласие родителя."""
    # Ищем существующее согласие
    existing = db.query(ParentalConsent).filter(
        ParentalConsent.student_id == data.student_id,
    ).first()

    if existing:
        existing.parent_email = data.parent_email
        existing.parent_name = data.parent_name
        existing.consent_given = data.consent_given
        existing.recording_allowed = data.recording_allowed
        existing.data_processing_allowed = data.data_processing_allowed
        if data.consent_given:
            existing.consent_date = datetime.now(timezone.utc)
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    consent = ParentalConsent(
        student_id=data.student_id,
        parent_email=data.parent_email,
        parent_name=data.parent_name,
        consent_given=data.consent_given,
        recording_allowed=data.recording_allowed,
        data_processing_allowed=data.data_processing_allowed,
        consent_date=datetime.now(timezone.utc) if data.consent_given else None,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent


@router.get("/student/{student_id}", response_model=ConsentResponse | None)
async def check_student_consent(
    student_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_teacher),
):
    """Проверить согласие родителя для ученика."""
    consent = db.query(ParentalConsent).filter(
        ParentalConsent.student_id == student_id,
    ).first()
    return consent


@router.get("/{consent_id}", response_model=ConsentResponse)
async def get_consent(
    consent_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_teacher),
):
    """Получить согласие по ID."""
    consent = db.query(ParentalConsent).filter(
        ParentalConsent.id == consent_id,
    ).first()
    if not consent:
        raise HTTPException(status_code=404, detail="Consent not found")
    return consent
