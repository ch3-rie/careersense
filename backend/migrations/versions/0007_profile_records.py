"""Seminars, certifications, awards, institution address, and employment notes.

Revision ID: 0007_profile_records
Revises: 0006_email_reminders
Create Date: 2026-10-19
"""

from alembic import op

revision = "0007_profile_records"
down_revision = "0006_email_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("ALTER TABLE further_studies DROP COLUMN IF EXISTS institution_address")
    op.execute("ALTER TABLE alumni_profiles DROP COLUMN IF EXISTS no_employment_reason")
    op.execute("DROP TABLE IF EXISTS alumni_awards")
    op.execute("DROP TABLE IF EXISTS alumni_certifications")
    op.execute("DROP TABLE IF EXISTS alumni_seminars")
