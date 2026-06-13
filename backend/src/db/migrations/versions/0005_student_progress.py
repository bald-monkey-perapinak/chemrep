"""Add student_progress table and summary column to lesson_sessions

Revision ID: 0005_student_progress
Revises: 0004_lesson_duration
Create Date: 2026-06-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0005_student_progress"
down_revision = "0004_lesson_duration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Таблица прогресса ученика
    op.create_table(
        "student_progress",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", UUID(as_uuid=True), sa.ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True),
        sa.Column("total_correct", sa.Integer(), server_default="0"),
        sa.Column("total_incorrect", sa.Integer(), server_default="0"),
        sa.Column("overall_confidence", sa.Float(), server_default="0.5"),
        sa.Column("weak_topics", JSONB(), server_default="[]"),
        sa.Column("strong_topics", JSONB(), server_default="[]"),
        sa.Column("common_errors", JSONB(), server_default="[]"),
        sa.Column("recommendations", JSONB(), server_default="[]"),
        sa.Column("student_model_snapshot", JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index("ix_student_progress_student_id", "student_progress", ["student_id"])

    # Поле summary в lesson_sessions
    op.add_column("lesson_sessions", sa.Column("summary", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("lesson_sessions", "summary")
    op.drop_index("ix_student_progress_student_id", table_name="student_progress")
    op.drop_table("student_progress")
