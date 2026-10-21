"""Optional salary range on alumni employment entries.

Revision ID: 0008_job_salary_range
Revises: 0007_profile_records
Create Date: 2026-10-20
"""

from alembic import op

revision = "0008_job_salary_range"
down_revision = "0007_profile_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("ALTER TABLE alumni_jobs DROP COLUMN IF EXISTS salary_range")
