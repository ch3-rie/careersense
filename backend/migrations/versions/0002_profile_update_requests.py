"""Profile update requests, recipients, and notification links.

Revision ID: 0002_profile_updates
Revises: 0001_integrity
Create Date: 2026-09-14
"""

from alembic import op

revision = "0002_profile_updates"
down_revision = "0001_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute("DROP TABLE IF EXISTS profile_update_request_recipients")
        op.execute("DROP TABLE IF EXISTS profile_update_requests")
        op.execute("ALTER TABLE alumni_notifications DROP COLUMN IF EXISTS link")
    else:
        op.execute("DROP TABLE IF EXISTS profile_update_request_recipients")
        op.execute("DROP TABLE IF EXISTS profile_update_requests")
