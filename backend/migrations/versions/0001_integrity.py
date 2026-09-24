"""Additive integrity columns and unique student-link index.

Revision ID: 0001_integrity
Revises:
Create Date: 2026-08-17
"""

from alembic import op

revision = "0001_integrity"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute("DROP INDEX IF EXISTS uq_accounts_linked_student_id")
        op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS password_changed_at")
    else:
        op.execute("DROP INDEX IF EXISTS uq_accounts_linked_student_id")
