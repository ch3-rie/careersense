"""Saved editable resume document on the alumni profile.

Revision ID: 0010_resume_document
Revises: 0009_unemployment_status
Create Date: 2026-10-21
"""

from alembic import op

revision = "0010_resume_document"
down_revision = "0009_unemployment_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("ALTER TABLE alumni_profiles DROP COLUMN IF EXISTS resume_document")
