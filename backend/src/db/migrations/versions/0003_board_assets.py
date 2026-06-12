"""Add topic_assets table, drop miro columns from knowledge_topics

Revision ID: 0003_board_assets
Revises: 0002_pgvector
Create Date: 2026-06-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_board_assets"
down_revision = "0002_pgvector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create topic_assets table
    op.create_table(
        "topic_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_name", sa.String(500), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("asset_type", sa.String(50), server_default="svg"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_topic_assets_topic_id", "topic_assets", ["topic_id"])

    # Drop miro columns
    op.drop_column("knowledge_topics", "miro_board_id")
    op.drop_column("knowledge_topics", "miro_board_url")


def downgrade() -> None:
    op.add_column("knowledge_topics", sa.Column("miro_board_id", sa.String(255), nullable=True))
    op.add_column("knowledge_topics", sa.Column("miro_board_url", sa.String(1000), nullable=True))
    op.drop_index("ix_topic_assets_topic_id", table_name="topic_assets")
    op.drop_table("topic_assets")
