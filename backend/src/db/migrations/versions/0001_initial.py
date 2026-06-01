"""Initial migration — create all tables

Revision ID: 0001_initial
Revises: —
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:

    # ── teachers ──────────────────────────────────────────────────────────────
    op.create_table(
        "teachers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(100), server_default="Химия"),
        sa.Column("voice_model_path", sa.String(500), nullable=True),
        sa.Column("voice_model_ready", sa.Boolean(), server_default="false"),
        sa.Column("default_vcs_platform", sa.String(50), server_default="zoom"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_teachers_email", "teachers", ["email"])

    # ── students ──────────────────────────────────────────────────────────────
    op.create_table(
        "students",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("grade", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_students_teacher_id", "students", ["teacher_id"])

    # ── knowledge_classes ─────────────────────────────────────────────────────
    op.create_table(
        "knowledge_classes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("grade_number", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── knowledge_sections ────────────────────────────────────────────────────
    op.create_table(
        "knowledge_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("class_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── knowledge_topics ──────────────────────────────────────────────────────
    op.create_table(
        "knowledge_topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("section_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("keywords", sa.String(500), nullable=True),
        sa.Column("lesson_script", postgresql.JSONB(), nullable=True),
        sa.Column("miro_board_id", sa.String(255), nullable=True),
        sa.Column("miro_board_url", sa.String(1000), nullable=True),
        sa.Column("estimated_duration_min", sa.Integer(), server_default="45"),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("is_published", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── topic_files ───────────────────────────────────────────────────────────
    op.create_table(
        "topic_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_name", sa.String(500), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("file_role", sa.String(50), server_default="material"),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("text_extracted", sa.Boolean(), server_default="false"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_topic_files_topic_id", "topic_files", ["topic_id"])

    # ── lessons ───────────────────────────────────────────────────────────────
    op.create_table(
        "lessons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vcs_platform", sa.String(50), nullable=False, server_default="zoom"),
        sa.Column("vcs_link", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="scheduled"),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("recording_path", sa.String(500), nullable=True),
        sa.Column("homework_sent", sa.Boolean(), server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_lessons_teacher_id", "lessons", ["teacher_id"])
    op.create_index("ix_lessons_scheduled_at", "lessons", ["scheduled_at"])

    # ── lesson_sessions ───────────────────────────────────────────────────────
    op.create_table(
        "lesson_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="starting"),
        sa.Column("current_step", sa.Integer(), server_default="0"),
        sa.Column("total_steps", sa.Integer(), nullable=True),
        sa.Column("dialog_history", postgresql.JSONB(), server_default="[]"),
        sa.Column("event_log", postgresql.JSONB(), server_default="[]"),
        sa.Column("bot_joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bot_left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── homeworks ─────────────────────────────────────────────────────────────
    op.create_table(
        "homeworks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("external_url", sa.String(1000), nullable=True),
        sa.Column("delivery_status", sa.String(50), server_default="pending"),
        sa.Column("delivery_channel", sa.String(50), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_error", sa.Text(), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("homeworks")
    op.drop_table("lesson_sessions")
    op.drop_table("lessons")
    op.drop_table("topic_files")
    op.drop_table("knowledge_topics")
    op.drop_table("knowledge_sections")
    op.drop_table("knowledge_classes")
    op.drop_table("students")
    op.drop_table("teachers")
