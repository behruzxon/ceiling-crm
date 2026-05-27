"""add_ai_user_memory

Revision ID: b9e3d2c1a0f7
Revises: 6819122e00b2
Create Date: 2026-02-19 00:01:00.000000+00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b9e3d2c1a0f7'
down_revision: str | None = '6819122e00b2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'ai_user_memory',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'profile',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default='{}',
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('user_id'),
    )


def downgrade() -> None:
    op.drop_table('ai_user_memory')
