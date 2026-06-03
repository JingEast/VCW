"""add prompt_versions table

Revision ID: 7410015efd2f
Revises: 5ee13a0f45ba
Create Date: 2026-05-29 20:29:09.850683
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7410015efd2f"
down_revision: Union[str, Sequence[str], None] = "5ee13a0f45ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgres():
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prompt_name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "prompt_name",
            "version",
            name="uq_prompt_version",
        ),
        sqlite_autoincrement=True,
    )

    op.create_index(
        op.f("ix_prompt_versions_prompt_name"),
        "prompt_versions",
        ["prompt_name"],
        unique=False,
    )

    #
    # embedding columns
    #
    if _is_postgres():
        try:
            op.execute("CREATE EXTENSION IF NOT EXISTS vector")

            op.execute(
                "ALTER TABLE memory_entries "
                "ADD COLUMN embedding VECTOR(1536)"
            )

            op.execute(
                "ALTER TABLE trends "
                "ADD COLUMN embedding VECTOR(1536)"
            )

        except Exception:
            #
            # CI 环境没有 pgvector 时降级
            #
            op.add_column(
                "memory_entries",
                sa.Column("embedding", sa.Text(), nullable=True),
            )

            op.add_column(
                "trends",
                sa.Column("embedding", sa.Text(), nullable=True),
            )

    else:
        #
        # SQLite
        #
        op.add_column(
            "memory_entries",
            sa.Column("embedding", sa.Text(), nullable=True),
        )

        op.add_column(
            "trends",
            sa.Column("embedding", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column("trends", "embedding")
    op.drop_column("memory_entries", "embedding")

    op.drop_index(
        op.f("ix_prompt_versions_prompt_name"),
        table_name="prompt_versions",
    )

    op.drop_table("prompt_versions")