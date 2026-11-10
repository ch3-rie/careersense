"""Optional speaker, mentor, and sponsor interest flags.

Revision ID: 0019_participation_interests
Revises: 0018_badge_images
Create Date: 2026-10-29
"""

from alembic import op

revision = "0019_participation_interests"
down_revision = "0018_badge_images"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("ALTER TABLE alumni_profiles DROP COLUMN interest_sponsor")
    op.execute("ALTER TABLE alumni_profiles DROP COLUMN interest_mentor")
    op.execute("ALTER TABLE alumni_profiles DROP COLUMN interest_speaker")
