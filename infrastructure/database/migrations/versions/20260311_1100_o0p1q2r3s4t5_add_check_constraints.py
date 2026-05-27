"""Add CHECK constraints for data integrity.

Revision ID: o0p1q2r3s4t5
Revises: n9o0p1q2r3s4
Create Date: 2026-03-11 11:00:00.000000

Changes
-------
1. payments.amount > 0  — prevent zero or negative payment amounts
2. leads.score >= 0     — score must be non-negative
3. leads.closing_confidence BETWEEN 0 AND 1 — probability range (nullable OK)
"""

from __future__ import annotations

from alembic import op

revision = "o0p1q2r3s4t5"
down_revision = "n9o0p1q2r3s4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_payments_amount_positive",
        "payments",
        "amount > 0",
    )
    op.create_check_constraint(
        "ck_leads_score_non_negative",
        "leads",
        "score >= 0",
    )
    op.create_check_constraint(
        "ck_leads_confidence_range",
        "leads",
        "closing_confidence IS NULL OR (closing_confidence >= 0 AND closing_confidence <= 1)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_leads_confidence_range", "leads", type_="check")
    op.drop_constraint("ck_leads_score_non_negative", "leads", type_="check")
    op.drop_constraint("ck_payments_amount_positive", "payments", type_="check")
