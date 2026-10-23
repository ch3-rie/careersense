"""Program kind, parent, and review status on the academic catalog.

Revision ID: 0013_program_review
Revises: 0012_academic_catalog
Create Date: 2026-10-22
"""

from alembic import op

revision = "0013_program_review"
down_revision = "0012_academic_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("ALTER TABLE academic_programs DROP COLUMN review_status")
    op.execute("ALTER TABLE academic_programs DROP COLUMN kind")
    op.execute("ALTER TABLE academic_programs DROP COLUMN parent_id")
