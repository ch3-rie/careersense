"""Editable college and course catalog.

Revision ID: 0012_academic_catalog
Revises: 0011_registry_imports
Create Date: 2026-10-22
"""

from alembic import op

revision = "0012_academic_catalog"
down_revision = "0011_registry_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS academic_programs")
    op.execute("DROP TABLE IF EXISTS colleges")
