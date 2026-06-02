"""add_perf_indexes_for_trends_jobs_memory

Revision ID: 20cfb7f0d6e2
Revises: 2eafbabfa56f
Create Date: 2026-06-02 12:32:29.700174

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20cfb7f0d6e2'
down_revision: Union[str, Sequence[str], None] = '2eafbabfa56f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes for trends, generation_jobs and memory_entries."""
    # trends: is_archived (practically every query filters on it)
    op.create_index("ix_trends_is_archived", "trends", ["is_archived"])
    # trends: category (filtered in get_all)
    op.create_index("ix_trends_category", "trends", ["category"])
    # trends: published_at (range filtered in time filters & delete_expired/stale)
    op.create_index("ix_trends_published_at", "trends", ["published_at"])
    # trends: fetched_at (range filtered alongside published_at)
    op.create_index("ix_trends_fetched_at", "trends", ["fetched_at"])
    # trends: composite index for the most common query pattern
    op.create_index("ix_trends_archived_published", "trends", ["is_archived", "published_at"])

    # generation_jobs: status (filtered in recover_on_startup, dead_letter scan, list_tasks)
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"])
    # generation_jobs: celery_task_id (looked up in async task service)
    op.create_index("ix_generation_jobs_celery_task_id", "generation_jobs", ["celery_task_id"])
    # generation_jobs: dead_letter (filtered in dead_letter_task)
    op.create_index("ix_generation_jobs_dead_letter", "generation_jobs", ["dead_letter"])
    # generation_jobs: created_at (ordered in list_tasks)
    op.create_index("ix_generation_jobs_created_at", "generation_jobs", ["created_at"])
    # generation_jobs: composite for batch children aggregation
    op.create_index("ix_generation_jobs_parent_status", "generation_jobs", ["parent_batch_id", "status"])

    # memory_entries: is_avoided (filtered in count_pending)
    op.create_index("ix_memory_entries_is_avoided", "memory_entries", ["is_avoided"])
    # memory_entries: created_at (ordered in get_recent_entries, get_entries_by_topic, get_entries_by_tags)
    op.create_index("ix_memory_entries_created_at", "memory_entries", ["created_at"])


def downgrade() -> None:
    """Drop performance indexes."""
    op.drop_index("ix_memory_entries_created_at", table_name="memory_entries")
    op.drop_index("ix_memory_entries_is_avoided", table_name="memory_entries")
    op.drop_index("ix_generation_jobs_parent_status", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_created_at", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_dead_letter", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_celery_task_id", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_status", table_name="generation_jobs")
    op.drop_index("ix_trends_archived_published", table_name="trends")
    op.drop_index("ix_trends_fetched_at", table_name="trends")
    op.drop_index("ix_trends_published_at", table_name="trends")
    op.drop_index("ix_trends_category", table_name="trends")
    op.drop_index("ix_trends_is_archived", table_name="trends")
