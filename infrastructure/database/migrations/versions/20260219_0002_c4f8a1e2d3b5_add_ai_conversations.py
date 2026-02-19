"""add_ai_conversations

Revision ID: c4f8a1e2d3b5
Revises: b9e3d2c1a0f7
Create Date: 2026-02-19 00:02:00.000000+00:00

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c4f8a1e2d3b5'
down_revision: Union[str, None] = 'b9e3d2c1a0f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_conversations',
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'last_messages',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default='[]',
            nullable=False,
        ),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column(
            'updated_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('user_id'),
    )


def downgrade() -> None:
    op.drop_table('ai_conversations')
