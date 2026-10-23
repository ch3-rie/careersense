"""Employee numbers, add-users privilege, and open-ended perk validity.

Revision ID: 0016_admin_access_perk_validity
Revises: 0015_partner_activities
Create Date: 2026-10-23
"""

from alembic import op

revision = "0016_admin_access_perk_validity"
down_revision = "0015_partner_activities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db import ensure_runtime_schema

    ensure_runtime_schema(op.get_bind())


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_accounts_employee_number")
    op.execute("ALTER TABLE accounts DROP COLUMN employee_number")
    op.execute("ALTER TABLE accounts DROP COLUMN admin_privileges")
    op.execute("ALTER TABLE alumni_perks DROP COLUMN valid_until_further_notice")
