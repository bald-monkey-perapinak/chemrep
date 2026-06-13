import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from src.db.base import Base


class ParentalConsent(Base):
    __tablename__ = "parental_consents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    parent_email = Column(String(255), nullable=False)
    parent_name = Column(String(255), nullable=False)
    consent_given = Column(Boolean, default=False)
    consent_date = Column(DateTime, nullable=True)
    recording_allowed = Column(Boolean, default=False)
    data_processing_allowed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
