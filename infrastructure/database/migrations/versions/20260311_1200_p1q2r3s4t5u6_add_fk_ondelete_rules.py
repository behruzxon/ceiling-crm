"""Add explicit ondelete rules to foreign keys.

Revision ID: p1q2r3s4t5u6
Revises: o0p1q2r3s4t5
Create Date: 2026-03-11 12:00:00.000000+00:00

FK ondelete decisions:
  CASCADE  — child records deleted with parent (pipeline_stages, appointments, quotes → leads)
  SET NULL — optional reference nulled on parent delete (leads.source_group_id, leads.assigned_manager_id,
             appointments.installer_id, audit_logs.actor_id)
  RESTRICT — prevent parent deletion while referenced (leads.user_id, pipeline_stages.changed_by,
             appointments.created_by, quotes.created_by, broadcasts.created_by)
"""

revision = "p1q2r3s4t5u6"
down_revision = "o0p1q2r3s4t5"
branch_labels = None
depends_on = None

from alembic import op

# (table, constraint_name, column, referred_table, referred_column, ondelete)
_FK_RULES: list[tuple[str, str, str, str, str, str]] = [
    # ── leads ────────────────────────────────────────────────────
    ("leads", "fk_leads_user_id",            "user_id",             "users",  "id", "RESTRICT"),
    ("leads", "fk_leads_source_group_id",    "source_group_id",     "groups", "id", "SET NULL"),
    ("leads", "fk_leads_assigned_manager_id","assigned_manager_id", "users",  "id", "SET NULL"),
    # ── pipeline_stages ──────────────────────────────────────────
    ("pipeline_stages", "fk_pipeline_stages_lead_id",    "lead_id",    "leads", "id", "CASCADE"),
    ("pipeline_stages", "fk_pipeline_stages_changed_by", "changed_by", "users", "id", "RESTRICT"),
    # ── appointments ─────────────────────────────────────────────
    ("appointments", "fk_appointments_lead_id",      "lead_id",      "leads", "id", "CASCADE"),
    ("appointments", "fk_appointments_installer_id", "installer_id", "users", "id", "SET NULL"),
    ("appointments", "fk_appointments_created_by",   "created_by",   "users", "id", "RESTRICT"),
    # ── quotes ───────────────────────────────────────────────────
    ("quotes", "fk_quotes_lead_id",    "lead_id",    "leads", "id", "CASCADE"),
    ("quotes", "fk_quotes_created_by", "created_by", "users", "id", "RESTRICT"),
    # ── broadcasts ───────────────────────────────────────────────
    ("broadcasts", "fk_broadcasts_created_by", "created_by", "users", "id", "RESTRICT"),
    # ── audit_logs ───────────────────────────────────────────────
    ("audit_logs", "fk_audit_logs_actor_id", "actor_id", "users", "id", "SET NULL"),
]


def _get_existing_fk_name(table: str, column: str) -> str:
    """Alembic auto-generated FK constraint name convention."""
    return f"{table}_{column}_fkey"


def upgrade() -> None:
    for table, new_name, column, ref_table, ref_col, ondelete in _FK_RULES:
        old_name = _get_existing_fk_name(table, column)
        op.drop_constraint(old_name, table, type_="foreignkey")
        op.create_foreign_key(
            new_name, table, ref_table,
            [column], [ref_col],
            ondelete=ondelete,
        )


def downgrade() -> None:
    for table, new_name, column, ref_table, ref_col, _ondelete in _FK_RULES:
        old_name = _get_existing_fk_name(table, column)
        op.drop_constraint(new_name, table, type_="foreignkey")
        op.create_foreign_key(
            old_name, table, ref_table,
            [column], [ref_col],
        )
