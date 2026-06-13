"""Add summary column to lesson_sessions

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('lesson_sessions', sa.Column('summary', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('lesson_sessions', 'summary')
