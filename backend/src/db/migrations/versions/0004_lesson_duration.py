"""Add duration_min column to lessons

Revision ID: 0004_lesson_duration
Revises: 0003_board_assets
Create Date: 2026-06-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_lesson_duration"
down_revision = "0003_board_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lessons", sa.Column("duration_min", sa.Integer(), server_default="60"))


def downgrade() -> None:
    op.drop_column("lessons", "duration_min")
