"""Partner visit, QR scan, and benefit redemption activity log.

Revision ID: 0015_partner_activities
Revises: 0014_badge_definitions
Create Date: 2026-10-23
"""

from alembic import op

revision = "0015_partner_activities"
down_revision = "0014_badge_definitions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS partner_activities")
