"""Add checkpoint columns to lesson_sessions

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('lesson_sessions', sa.Column('checkpoint_step', sa.Integer(), nullable=True))
    op.add_column('lesson_sessions', sa.Column('checkpoint_state', sa.Text(), nullable=True))
    op.add_column('lesson_sessions', sa.Column('checkpoint_time', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('lesson_sessions', 'checkpoint_time')
    op.drop_column('lesson_sessions', 'checkpoint_state')
    op.drop_column('lesson_sessions', 'checkpoint_step')
