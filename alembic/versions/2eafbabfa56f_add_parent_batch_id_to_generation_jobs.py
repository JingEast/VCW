"""add parent_batch_id to generation_jobs

Revision ID: 2eafbabfa56f
Revises: 8f3bb9584a0c
Create Date: 2026-05-31 19:38:57.022365

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2eafbabfa56f'
down_revision: Union[str, Sequence[str], None] = '8f3bb9584a0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('generation_jobs', sa.Column('parent_batch_id', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_generation_jobs_parent_batch_id'), 'generation_jobs', ['parent_batch_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_generation_jobs_parent_batch_id'), table_name='generation_jobs')
    op.drop_column('generation_jobs', 'parent_batch_id')
