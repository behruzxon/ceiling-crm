"""Tests for Step AZ — CRMEnrichmentService."""
from __future__ import annotations
from core.services.crm_enrichment_service import CRMEnrichmentService

svc = CRMEnrichmentService

class TestPhone:
    def test_full(self): assert svc.extract_phone("+998901234567") == "+998901234567"
    def test_local(self): assert svc.extract_phone("901234567") == "+998901234567"
    def test_none(self): assert svc.extract_phone("salom") is None

class TestArea:
    def test_20kv(self): assert svc.extract_area_m2("20 kv") == 20.0
    def test_5x4(self): assert svc.extract_area_m2("5x4") == 20.0
    def test_30m2(self): assert svc.extract_area_m2("30 m2") == 30.0
    def test_none(self): assert svc.extract_area_m2("salom") is None

class TestCeiling:
    def test_gulli(self): assert svc.extract_ceiling_type("gulli potalok") == "gulli"
    def test_matoviy(self): assert svc.extract_ceiling_type("matoviy kerak") == "matoviy"
    def test_led(self): assert svc.extract_ceiling_type("led potolok") == "led"
    def test_mramor(self): assert svc.extract_ceiling_type("mramor turini") == "mramor"
    def test_none(self): assert svc.extract_ceiling_type("salom") is None

class TestLocation:
    def test_qarshi(self): assert svc.extract_location("men qarshidanman") == "qarshi"
    def test_shahrisabz(self): assert svc.extract_location("shahrisabzda yashayman") == "shahrisabz"
    def test_none(self): assert svc.extract_location("salom") is None

class TestBudget:
    def test_3mln(self): assert svc.extract_budget_hint("3 mln budjet") is not None
    def test_arzon(self): assert svc.extract_budget_hint("arzonroq bo'lsa") == "arzon"
    def test_qimmat(self): assert svc.extract_budget_hint("qimmat ekan") == "qimmat"
    def test_none(self): assert svc.extract_budget_hint("salom") is None

class TestEnrichFromText:
    def test_multiple(self):
        r = svc.enrich_from_text("Men qarshidanman, 20 kv gulli potalok kerak")
        assert r.get("district") == "qarshi"
        assert r.get("area_m2") == 20.0
        assert r.get("ceiling_type") == "gulli"

    def test_phone(self):
        r = svc.enrich_from_text("telefon 901234567")
        assert r.get("phone") == "+998901234567"

    def test_empty(self):
        assert svc.enrich_from_text("salom") == {}

class TestEnrichFromSignal:
    def test_intent(self):
        r = svc.enrich_from_signal({"intent": "wants_price"})
        assert r["last_intent"] == "wants_price"

    def test_objection(self):
        r = svc.enrich_from_signal({"objection_type": "price"})
        assert r["objection_type"] == "price"

    def test_area(self):
        r = svc.enrich_from_signal({"area_m2": 20.0})
        assert r["area_m2"] == 20.0

class TestMarketingDisable:
    def test_stop(self): assert svc.should_disable_marketing({"intent": "stop_request"})
    def test_normal(self): assert not svc.should_disable_marketing({"intent": "wants_price"})
