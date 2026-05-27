"""Add system_errors table for global exception logging.

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-03-11 13:00:00.000000+00:00
"""

revision = "q2r3s4t5u6v7"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        "system_errors",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("service", sa.String(64), nullable=False),
        sa.Column("error_type", sa.String(256), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("stacktrace", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_system_errors_service", "system_errors", ["service"])
    op.create_index("ix_system_errors_created_at", "system_errors", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_system_errors_created_at", table_name="system_errors")
    op.drop_index("ix_system_errors_service", table_name="system_errors")
    op.drop_table("system_errors")
