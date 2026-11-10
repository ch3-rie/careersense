"""Upload timestamp for graduate registry rows.

Revision ID: 0017_registry_uploaded_at
Revises: 0016_admin_access_perk_validity
Create Date: 2026-10-29
"""

from alembic import op

revision = "0017_registry_uploaded_at"
down_revision = "0016_admin_access_perk_validity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("ALTER TABLE university_records DROP COLUMN uploaded_at")
