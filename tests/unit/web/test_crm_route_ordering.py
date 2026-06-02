"""Regression: static CRM pages must not be swallowed by /crm/{contact_id}.

The dynamic contact-detail route uses the ``:int`` path converter so named CRM
pages (/crm/missed-leads, /crm/handoffs, /crm/campaigns, ...) resolve to their own
handlers instead of failing with int_parsing on ``contact_id``. We assert at the
router level (no handler execution, no API/network) which endpoint each path maps to.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.routing import Match

from apps.web.main import app


def _resolve(path: str) -> str | None:
    scope = {"type": "http", "method": "GET", "path": path}
    for route in app.routes:
        if not hasattr(route, "matches"):
            continue
        match, _ = route.matches(scope)
        if match == Match.FULL:
            return getattr(route, "name", None) or getattr(
                getattr(route, "endpoint", None), "__name__", None
            )
    return None


class TestStaticCrmPagesResolve:
    @pytest.mark.parametrize(
        "path,endpoint",
        [
            ("/crm/missed-leads", "crm_missed_leads"),
            ("/crm/handoffs", "crm_handoffs"),
            ("/crm/campaigns", "crm_campaigns"),
            ("/crm/operator-digest", "crm_operator_digest"),
            ("/crm/inbox", "crm_inbox"),
        ],
    )
    def test_named_page_not_contact_detail(self, path, endpoint):
        got = _resolve(path)
        assert got == endpoint, f"{path} resolved to {got}, expected {endpoint}"
        assert got != "crm_contact_detail"


class TestDynamicContactRouteStillWorks:
    @pytest.mark.parametrize("path", ["/crm/1", "/crm/42", "/crm/123456789"])
    def test_integer_id_resolves_to_detail(self, path):
        assert _resolve(path) == "crm_contact_detail"

    def test_crm_root_is_contacts_list(self):
        assert _resolve("/crm") == "crm_contacts"


class TestNonIntegerContactPathDoesNotMatchDetail:
    @pytest.mark.parametrize(
        "seg", ["missed-leads", "handoffs", "campaigns", "operator-digest", "inbox"]
    )
    def test_string_segment_never_hits_int_route(self, seg):
        # If a string slipped into /crm/{contact_id:int} it would 422; instead it
        # must resolve to the named page (or None), never crm_contact_detail.
        assert _resolve(f"/crm/{seg}") != "crm_contact_detail"


class TestSourcePins:
    def _src(self) -> str:
        return Path("apps/web/main.py").read_text(encoding="utf-8")

    def test_dynamic_route_constrained_to_int(self):
        assert '"/crm/{contact_id:int}"' in self._src()

    def test_no_unconstrained_contact_route(self):
        # The old, ambiguous pattern must be gone.
        assert '"/crm/{contact_id}"' not in self._src()
