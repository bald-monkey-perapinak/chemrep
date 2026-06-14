"""Add parent_telegram_chat_id to parental_consents

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('parental_consents', sa.Column('parent_telegram_chat_id', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('parental_consents', 'parent_telegram_chat_id')
