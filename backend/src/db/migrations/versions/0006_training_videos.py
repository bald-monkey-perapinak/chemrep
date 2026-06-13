"""Add training_videos and teaching_profiles tables

Revision ID: 0006_training_videos
Revises: 0005_student_progress
Create Date: 2026-06-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0006_training_videos"
down_revision = "0005_student_progress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Таблица обучающих видео
    op.create_table(
        "training_videos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("teacher_id", UUID(as_uuid=True), sa.ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_name", sa.String(500), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), server_default="uploading"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("audio_path", sa.String(1000), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("teaching_profile", JSONB(), nullable=True),
        sa.Column("progress", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index("ix_training_videos_teacher_id", "training_videos", ["teacher_id"])

    # Таблица профилей стиля преподавания
    op.create_table(
        "teaching_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("teacher_id", UUID(as_uuid=True), sa.ForeignKey("teachers.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("profile", JSONB(), server_default="{}"),
        sa.Column("videos_count", sa.Integer(), server_default="0"),
        sa.Column("total_duration_min", sa.Float(), server_default="0"),
        sa.Column("custom_prompt", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("teaching_profiles")
    op.drop_index("ix_training_videos_teacher_id", table_name="training_videos")
    op.drop_table("training_videos")
