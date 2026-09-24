"""Password reset PIN verifications.

Revision ID: 0003_password_reset
Revises: 0002_profile_updates
Create Date: 2026-09-14
"""

from alembic import op

revision = "0003_password_reset"
down_revision = "0002_profile_updates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS password_reset_verifications")
