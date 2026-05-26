"""Tests for Step AZ — CRMSegmentService."""
from __future__ import annotations
from core.services.crm_segment_service import CRMSegmentService

svc = CRMSegmentService

def _c(**kw):
    defaults = {"lead_status": "active", "temperature": "warm", "metadata_json": {}}
    defaults.update(kw)
    return defaults

class TestSegments:
    def test_hot(self): assert "hot_leads" in svc.build_contact_segments(_c(temperature="hot"))
    def test_phone(self): assert "phone_shared" in svc.build_contact_segments(_c(phone="+998"))
    def test_stopped(self): assert "stopped_users" in svc.build_contact_segments(_c(lead_status="stopped"))
    def test_price(self): assert "price_interested" in svc.build_contact_segments(_c(metadata_json={"last_intent": "wants_price"}))
    def test_operator(self): assert "operator_requested" in svc.build_contact_segments(_c(metadata_json={"last_intent": "wants_operator"}))
    def test_order(self): assert "order_started" in svc.build_contact_segments(_c(metadata_json={"last_intent": "wants_order"}))
    def test_obj_price(self): assert "objection_price" in svc.build_contact_segments(_c(metadata_json={"objection_type": "price"}))
    def test_obj_trust(self): assert "objection_trust" in svc.build_contact_segments(_c(metadata_json={"objection_type": "trust"}))
    def test_location(self): assert "location_known" in svc.build_contact_segments(_c(district="Qarshi"))
    def test_area(self): assert "area_known" in svc.build_contact_segments(_c(area_m2=20.0))
    def test_ceiling(self): assert "ceiling_type_known" in svc.build_contact_segments(_c(ceiling_type="gulli"))
    def test_marketing(self): assert "marketing_allowed" in svc.build_contact_segments(_c())

class TestMarketing:
    def test_stopped_no(self): assert not svc.is_marketing_allowed(_c(lead_status="stopped"))
    def test_lost_no(self): assert not svc.is_marketing_allowed(_c(lead_status="lost"))
    def test_disabled_no(self): assert not svc.is_marketing_allowed(_c(marketing_allowed=False))
    def test_followup_no(self): assert not svc.is_marketing_allowed(_c(followup_allowed=False))
    def test_active_yes(self): assert svc.is_marketing_allowed(_c())

class TestNextOffer:
    def test_operator(self): assert svc.build_next_best_offer(_c(metadata_json={"last_intent": "wants_operator"}))
    def test_phone(self): assert svc.build_next_best_offer(_c(phone="+998"))
    def test_price_obj(self): assert svc.build_next_best_offer(_c(metadata_json={"objection_type": "price"}))
    def test_area(self): assert svc.build_next_best_offer(_c(area_m2=20))
    def test_none(self): assert svc.build_next_best_offer(_c()) is None

class TestValid:
    def test_valid(self): assert svc.is_valid_segment("hot_leads")
    def test_invalid(self): assert not svc.is_valid_segment("random")
