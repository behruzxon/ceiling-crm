"""Fix group_join_events unique constraint to include tenant_id.

The old constraint (group_id, user_id) was globally unique,
preventing different tenants from tracking the same (group, user) pair.
The new constraint (group_id, user_id, tenant_id) is per-tenant.

Revision ID: y1z2a3b4c5d6
Revises: x9y0z1a2b3c4
Create Date: 2026-03-09 18:00:00.000000+00:00
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "y1z2a3b4c5d6"
down_revision = "x9y0z1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old global unique constraint
    op.drop_constraint(
        "uq_group_join_events_group_user",
        "group_join_events",
        type_="unique",
    )
    # Create new tenant-scoped unique constraint
    op.create_unique_constraint(
        "uq_group_join_events_group_user_tenant",
        "group_join_events",
        ["group_id", "user_id", "tenant_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_group_join_events_group_user_tenant",
        "group_join_events",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_group_join_events_group_user",
        "group_join_events",
        ["group_id", "user_id"],
    )
