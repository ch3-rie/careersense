"""Optional custom image for badge definitions.

Revision ID: 0018_badge_images
Revises: 0017_registry_uploaded_at
Create Date: 2026-10-29
"""

from alembic import op

revision = "0018_badge_images"
down_revision = "0017_registry_uploaded_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("ALTER TABLE badge_definitions DROP COLUMN image_mime")
    op.execute("ALTER TABLE badge_definitions DROP COLUMN image_path")
