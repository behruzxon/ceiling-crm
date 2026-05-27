"""add_group_settings

Per-group moderation settings table for C3 Group Admin Mode.

Revision ID: e1f2a3b4c5d6
Revises: d5e8f1a2b3c4
Create Date: 2026-02-25 12:00:00.000000+00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: str | None = 'd5e8f1a2b3c4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'group_settings',
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('welcome_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('welcome_autodelete_seconds', sa.Integer(), server_default='45', nullable=False),
        sa.Column('captcha_enabled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('link_block_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('flood_enabled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('logs_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column(
            'updated_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('chat_id'),
    )


def downgrade() -> None:
    op.drop_table('group_settings')
