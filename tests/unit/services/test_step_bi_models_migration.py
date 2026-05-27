"""Tests for Step BI — DB models, migration, and schema imports."""

from __future__ import annotations

import importlib


class TestModels:
    def test_admin_user_model_importable(self):
        from infrastructure.database.models.admin_user import AdminUserModel

        assert AdminUserModel.__tablename__ == "admin_users"

    def test_admin_audit_log_model_importable(self):
        from infrastructure.database.models.admin_user import AdminAuditLogModel

        assert AdminAuditLogModel.__tablename__ == "admin_audit_logs"

    def test_admin_user_columns(self):
        from infrastructure.database.models.admin_user import AdminUserModel

        cols = {c.name for c in AdminUserModel.__table__.columns}
        assert "admin_id" in cols
        assert "role" in cols
        assert "is_active" in cols
        assert "is_super_owner" in cols
        assert "permissions_override_json" in cols
        assert "last_seen_at" in cols
        assert "disabled_at" in cols

    def test_admin_audit_log_columns(self):
        from infrastructure.database.models.admin_user import AdminAuditLogModel

        cols = {c.name for c in AdminAuditLogModel.__table__.columns}
        assert "actor_admin_id" in cols
        assert "actor_role" in cols
        assert "action" in cols
        assert "target_type" in cols
        assert "target_id" in cols
        assert "status" in cols
        assert "reason" in cols
        assert "metadata_json" in cols

    def test_admin_user_unique_admin_id(self):
        from infrastructure.database.models.admin_user import AdminUserModel

        col = AdminUserModel.__table__.c.admin_id
        assert col.unique is True


class TestMigration:
    def test_importable(self):
        mod = importlib.import_module(
            "infrastructure.database.migrations.versions."
            "20260526_1535_d5e6f7g8h9i0_add_admin_users_audit_logs"
        )
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)

    def test_revision(self):
        mod = importlib.import_module(
            "infrastructure.database.migrations.versions."
            "20260526_1535_d5e6f7g8h9i0_add_admin_users_audit_logs"
        )
        assert mod.revision == "d5e6f7g8h9i0"


class TestSchemas:
    def test_admin_user_record(self):
        from core.schemas.admin_user import AdminUserRecord

        r = AdminUserRecord(admin_id="test1", role="admin")
        assert r.admin_id == "test1"
        assert r.role == "admin"

    def test_admin_user_record_frozen(self):
        import pytest

        from core.schemas.admin_user import AdminUserRecord

        r = AdminUserRecord()
        with pytest.raises(AttributeError):
            r.admin_id = "x"  # type: ignore[misc]

    def test_admin_user_create_request(self):
        from core.schemas.admin_user import AdminUserCreateRequest

        r = AdminUserCreateRequest(admin_id="u1", role="viewer")
        assert r.admin_id == "u1"

    def test_admin_user_update_request(self):
        from core.schemas.admin_user import AdminUserUpdateRequest

        r = AdminUserUpdateRequest(role="admin", updated_by="own1")
        assert r.role == "admin"

    def test_admin_audit_entry(self):
        from core.schemas.admin_user import AdminAuditEntry

        e = AdminAuditEntry(action="test", status="success")
        assert e.action == "test"

    def test_admin_audit_entry_frozen(self):
        import pytest

        from core.schemas.admin_user import AdminAuditEntry

        e = AdminAuditEntry()
        with pytest.raises(AttributeError):
            e.action = "x"  # type: ignore[misc]

    def test_service_result(self):
        from core.schemas.admin_user import AdminUserServiceResult

        r = AdminUserServiceResult(ok=True)
        assert r.ok

    def test_service_result_frozen(self):
        import pytest

        from core.schemas.admin_user import AdminUserServiceResult

        r = AdminUserServiceResult()
        with pytest.raises(AttributeError):
            r.ok = True  # type: ignore[misc]
