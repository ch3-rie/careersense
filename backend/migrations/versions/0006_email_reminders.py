"""Email outbox retries and automated profile reminder settings.

Revision ID: 0006_email_reminders
Revises: 0005_achievement_metadata
Create Date: 2026-09-20
"""

from alembic import op

revision = "0006_email_reminders"
down_revision = "0005_achievement_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS profile_reminder_sends")
    op.execute("DROP TABLE IF EXISTS profile_reminder_runs")
    op.execute("DROP TABLE IF EXISTS profile_reminder_settings")
    op.execute("DROP TABLE IF EXISTS email_outbox")
