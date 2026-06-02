"""Regression: /crm/handoffs must render with the API's dict response.

The API returns ``{"items": [...], "count": N}``. The template previously used
``queue.items`` which Jinja resolves to the dict's ``.items()`` *method*, raising
``TypeError: 'builtin_function_or_method' object is not iterable`` at render time
(it only surfaced once the route stopped 422-ing). These tests render the real
template through the app's Jinja env with a dict queue — offline, no API/network.
"""

from __future__ import annotations

from pathlib import Path

from apps.web.main import templates

_SUMMARY = {
    "total_open": 2,
    "total_waiting_phone": 1,
    "total_assigned": 0,
    "total_urgent": 1,
    "total_high": 0,
}


def _render(queue):
    tpl = templates.get_template("crm_handoffs.html")
    return tpl.render(
        {
            "request": None,
            "summary": _SUMMARY,
            "queue": queue,
            "status_filter": "",
            "priority_filter": "",
            "active_page": "handoffs",
        }
    )


class TestRendersWithDictQueue:
    def test_renders_with_items(self):
        html = _render(
            {
                "items": [
                    {
                        "id": 1,
                        "priority": "urgent",
                        "status": "open",
                        "reason": "operator_requested",
                        "phone_masked": "+998****67",
                        "district": "Qarshi",
                        "created_at": "2026-06-02T10:00:00",
                    }
                ],
                "count": 1,
            }
        )
        assert "Handoff" in html or "handoff" in html.lower()
        assert html.count("<tr>") >= 2  # header + one data row

    def test_renders_empty_queue(self):
        html = _render({"items": [], "count": 0})
        assert "<table" not in html or "vp-empty" in html  # empty state, no crash

    def test_renders_none_queue(self):
        # A failed/empty API fetch must not crash the page.
        html = _render(None)
        assert html  # rendered something, no exception

    def test_renders_missing_items_key(self):
        html = _render({"count": 0})
        assert html

    def test_multiple_rows(self):
        items = [
            {
                "id": i,
                "priority": "normal",
                "status": "assigned",
                "created_at": "2026-06-02T10:00:00",
            }
            for i in range(3)
        ]
        html = _render({"items": items, "count": 3})
        assert html.count("<tr>") >= 4  # header + 3


class TestSourcePin:
    def _t(self) -> str:
        return Path("apps/web/templates/crm_handoffs.html").read_text(encoding="utf-8")

    def test_no_dict_items_method_access(self):
        # The buggy `queue.items` pattern must be gone.
        assert "queue.items" not in self._t()

    def test_uses_get_items(self):
        assert '.get("items"' in self._t()


class TestRouteStillStatic:
    def test_handoffs_route_resolves(self):
        from starlette.routing import Match

        from apps.web.main import app

        scope = {"type": "http", "method": "GET", "path": "/crm/handoffs"}
        names = [
            getattr(r, "name", None)
            for r in app.routes
            if hasattr(r, "matches") and r.matches(scope)[0] == Match.FULL
        ]
        assert "crm_handoffs" in names
