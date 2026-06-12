"""Add pgvector extension and content_embeddings table

Revision ID: 0002_pgvector
Revises: 0001_initial
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = "0002_pgvector"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── pgvector extension ─────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── content_embeddings ─────────────────────────────────────────────────
    op.create_table(
        "content_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), server_default="0"),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("embedding_json", sa.Text(), nullable=True),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_topics.id", ondelete="CASCADE"), nullable=True),
        sa.Column("teacher_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_embeddings_source", "content_embeddings", ["source_type", "source_id"])
    op.create_index("ix_embeddings_topic_id", "content_embeddings", ["topic_id"])
    op.create_index("ix_embeddings_teacher_id", "content_embeddings", ["teacher_id"])

    # HNSW index for fast approximate nearest neighbor search
    op.execute(
        "CREATE INDEX ix_embeddings_vector ON content_embeddings "
        " USING hnsw (embedding vector_cosine_ops) "
        " WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_embeddings_vector")
    op.drop_table("content_embeddings")
    op.execute("DROP EXTENSION IF EXISTS vector")
