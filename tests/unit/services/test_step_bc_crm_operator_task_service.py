"""Tests for Step BC — CRMOperatorTaskService."""
from __future__ import annotations

from core.services.crm_operator_task_service import CRMOperatorTaskService, TaskRecommendation

svc = CRMOperatorTaskService

def _c(*, status="active", temp="warm", intent=None, objection=None, phone=None, name="Test", cid=1):
    md = {}
    if intent: md["last_intent"] = intent
    if objection: md["objection_type"] = objection
    return {"id": cid, "first_name": name, "lead_status": status,
            "temperature": temp, "phone": phone, "metadata_json": md}


class TestValidation:
    def test_valid_types(self):
        for t in ("reply", "call", "follow_up", "measurement", "price_offer", "custom"):
            assert svc.is_valid_type(t)
    def test_invalid_type(self): assert not svc.is_valid_type("random")
    def test_valid_statuses(self):
        for s in ("todo", "in_progress", "done", "snoozed", "cancelled"):
            assert svc.is_valid_status(s)
    def test_invalid_status(self): assert not svc.is_valid_status("random")
    def test_valid_priorities(self):
        for p in ("low", "normal", "high", "urgent"):
            assert svc.is_valid_priority(p)
    def test_invalid_priority(self): assert not svc.is_valid_priority("random")

class TestValidateCreate:
    def test_valid(self):
        ok, _ = svc.validate_create("Call Aziz", "call")
        assert ok
    def test_empty_title(self):
        ok, r = svc.validate_create("", "call")
        assert not ok and "empty" in r
    def test_long_title(self):
        ok, r = svc.validate_create("x" * 201, "call")
        assert not ok
    def test_invalid_type(self):
        ok, r = svc.validate_create("Task", "random")
        assert not ok
    def test_invalid_priority(self):
        ok, r = svc.validate_create("Task", "call", "mega")
        assert not ok

class TestRecommendations:
    def test_critical_sla(self):
        r = svc.recommend_task_for_contact(_c(), alert_type="critical_sla")
        assert r is not None and r.priority == "urgent" and r.task_type == "reply"

    def test_hot_unanswered(self):
        r = svc.recommend_task_for_contact(_c(), alert_type="hot_unanswered")
        assert r is not None and r.priority == "urgent"

    def test_operator_needed(self):
        r = svc.recommend_task_for_contact(_c(), alert_type="operator_needed")
        assert r is not None and r.task_type == "call"

    def test_phone_shared(self):
        r = svc.recommend_task_for_contact(_c(), alert_type="phone_shared_unanswered")
        assert r is not None and r.task_type == "call" and r.priority == "high"

    def test_overdue(self):
        r = svc.recommend_task_for_contact(_c(), alert_type="overdue")
        assert r is not None and r.priority == "high"

    def test_price_interested(self):
        r = svc.recommend_task_for_contact(_c(intent="wants_price"))
        assert r is not None and r.task_type == "price_offer"

    def test_price_objection(self):
        r = svc.recommend_task_for_contact(_c(objection="price"))
        assert r is not None and r.task_type == "follow_up"

    def test_stopped_none(self):
        assert svc.recommend_task_for_contact(_c(status="stopped")) is None

    def test_lost_none(self):
        assert svc.recommend_task_for_contact(_c(status="lost")) is None

    def test_won_none(self):
        assert svc.recommend_task_for_contact(_c(status="won")) is None

    def test_no_alert_no_intent(self):
        assert svc.recommend_task_for_contact(_c()) is None

    def test_title_contains_name(self):
        r = svc.recommend_task_for_contact(_c(name="Aziz"), alert_type="critical_sla")
        assert "Aziz" in r.title

    def test_reason_not_empty(self):
        r = svc.recommend_task_for_contact(_c(), alert_type="hot_unanswered")
        assert r.reason

class TestRecommendFromAlerts:
    def test_empty(self):
        assert svc.recommend_tasks_from_alerts([], {}) == []

    def test_with_alerts(self):
        alerts = [{"contact_id": 1, "alert_type": "critical_sla", "severity": "critical"}]
        contacts = {1: _c(cid=1)}
        recs = svc.recommend_tasks_from_alerts(alerts, contacts)
        assert len(recs) == 1

    def test_stopped_filtered(self):
        alerts = [{"contact_id": 1, "alert_type": "critical_sla"}]
        contacts = {1: _c(status="stopped", cid=1)}
        assert svc.recommend_tasks_from_alerts(alerts, contacts) == []

class TestPriorityCalc:
    def test_critical(self): assert svc.calculate_task_priority(_c(), "critical") == "urgent"
    def test_danger(self): assert svc.calculate_task_priority(_c(), "danger") == "high"
    def test_hot(self): assert svc.calculate_task_priority(_c(temp="hot")) == "high"
    def test_warm(self): assert svc.calculate_task_priority(_c(temp="warm")) == "normal"
    def test_cold(self): assert svc.calculate_task_priority(_c(temp="cold")) == "low"

class TestModel:
    def test_importable(self):
        from infrastructure.database.models.crm_operator_task import CRMOperatorTaskModel
        assert CRMOperatorTaskModel.__tablename__ == "crm_operator_tasks"

class TestMigration:
    def test_importable(self):
        import importlib
        mod = importlib.import_module(
            "infrastructure.database.migrations.versions."
            "20260526_1440_a2b3c4d5e6f7_add_crm_operator_tasks"
        )
        assert callable(mod.upgrade)

class TestImmutability:
    def test_frozen(self):
        import pytest
        r = TaskRecommendation()
        with pytest.raises(AttributeError):
            r.priority = "x"  # type: ignore[misc]
