"""add processing_stage column

Revision ID: 069da6a96bbb
Revises: 001
Create Date: 2026-09-19 22:17:29.718504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '069da6a96bbb'
down_revision: Union[str, Sequence[str], None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('memories', sa.Column('processing_stage', sa.String(length=50), server_default='uploaded', nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('memories', 'processing_stage')
