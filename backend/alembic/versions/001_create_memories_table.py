"""create memories table

Revision ID: 001
Revises: 
Create Date: 2025-09-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("s3_key", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("processing_status", sa.String(50), nullable=False, server_default="uploaded"),
        sa.Column("moderation_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("metadata_", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("s3_key"),
    )
    op.create_index("ix_memories_s3_key", "memories", ["s3_key"], unique=True)
    op.create_index("ix_memories_processing_status", "memories", ["processing_status"])
    op.create_index("ix_memories_created_at", "memories", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_memories_created_at", table_name="memories")
    op.drop_index("ix_memories_processing_status", table_name="memories")
    op.drop_index("ix_memories_s3_key", table_name="memories")
    op.drop_table("memories")