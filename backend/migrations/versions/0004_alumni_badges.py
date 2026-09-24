"""Alumni profile-completion badges.

Revision ID: 0004_alumni_badges
Revises: 0003_password_reset
Create Date: 2026-09-15
"""

from alembic import op

revision = "0004_alumni_badges"
down_revision = "0003_password_reset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS alumni_badges")
