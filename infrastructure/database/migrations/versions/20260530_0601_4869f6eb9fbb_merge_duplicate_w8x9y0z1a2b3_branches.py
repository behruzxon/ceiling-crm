"""merge duplicate w8x9y0z1a2b3 branches

Revision ID: 4869f6eb9fbb
Revises: w8x9y0z1a2b3a, n1o2p3q4r5s6
Create Date: 2026-05-30 06:01:48.541132+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4869f6eb9fbb"
down_revision: str | None = ("w8x9y0z1a2b3a", "n1o2p3q4r5s6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
