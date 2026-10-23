"""Graduate list import batches.

Revision ID: 0011_registry_imports
Revises: 0010_resume_document
Create Date: 2026-10-22
"""

from alembic import op

revision = "0011_registry_imports"
down_revision = "0010_resume_document"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS registry_imports")
