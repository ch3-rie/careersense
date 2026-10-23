"""Badge catalog managed by OAAPS administrators.

Revision ID: 0014_badge_definitions
Revises: 0013_program_review
Create Date: 2026-10-23
"""

from alembic import op

revision = "0014_badge_definitions"
down_revision = "0013_program_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS badge_definitions")
