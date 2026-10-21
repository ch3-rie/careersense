"""Current unemployment status on the alumni profile.

Revision ID: 0009_unemployment_status
Revises: 0008_job_salary_range
Create Date: 2026-10-20
"""

from alembic import op

revision = "0009_unemployment_status"
down_revision = "0008_job_salary_range"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("ALTER TABLE alumni_profiles DROP COLUMN IF EXISTS currently_unemployed")
    op.execute("ALTER TABLE alumni_profiles DROP COLUMN IF EXISTS unemployment_reason")
    op.execute("ALTER TABLE alumni_profiles DROP COLUMN IF EXISTS unemployment_details")
    op.execute("ALTER TABLE alumni_profiles DROP COLUMN IF EXISTS employment_answer_before")
