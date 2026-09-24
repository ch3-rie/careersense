"""Optional achievement award metadata.

Revision ID: 0005_achievement_metadata
Revises: 0004_alumni_badges
Create Date: 2026-09-15
"""

from alembic import op

revision = "0005_achievement_metadata"
down_revision = "0004_alumni_badges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        return
    op.execute("ALTER TABLE alumni_badges DROP COLUMN IF EXISTS award_metadata")
