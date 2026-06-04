"""Admin/Operator UX polish — Uzbek labels, honest error states, range toggle.

Pure template-source assertions (no DB/Redis/network). These pin the
business-owner-facing polish added in feat/admin-operator-ux-polish:

* shared nav/topbar/footer translated to Uzbek (routes/URLs unchanged)
* analytics lead-lifecycle labels translated; real trend range toggle added
* missed-leads severity tiers in Uzbek; phone masking preserved
* operator pages that previously failed silently now show an error banner
  (never a false "all clear" when the API call fails)
"""

from __future__ import annotations

from pathlib import Path

TPL = Path("apps/web/templates")


def _read(name: str) -> str:
    return (TPL / name).read_text(encoding="utf-8")


# ───────────────────────────── shared nav / chrome ──────────────────────────


class TestBaseNavUzbek:
    def test_nav_labels_translated(self) -> None:
        c = _read("base.html")
        for label in (
            "Boshqaruv paneli",  # Dashboard
            "Savdo bosqichlari",  # Pipeline
            "Leadlar",  # Leads
            "Javobsiz leadlar",  # Missed Leads
            "Operator navbati",  # Handoffs
            "Kampaniyalar",  # Campaigns
            "Tahlillar",  # Analytics
            "Bilimlar bazasi",  # Knowledge Base
            "Noma'lum savollar",  # Unknown Questions
            "Xavfsizlik",  # Security
            "Yordam",  # Help
        ):
            assert label in c, label

    def test_footer_translated(self) -> None:
        c = _read("base.html")
        assert "Xavfsiz rejim" in c  # was "Safe mode"
        assert "Avto-yuborish o'chiq" in c  # was "Flags OFF"

    def test_old_english_nav_removed(self) -> None:
        c = _read("base.html")
        # link text + footer that used to be English are gone
        for stale in ("Safe mode", "Flags OFF", "Handoff Queue", "Knowledge Base"):
            assert stale not in c, stale

    def test_routes_and_urls_unchanged(self) -> None:
        c = _read("base.html")
        for href in (
            'href="/dashboard"',
            'href="/pipeline"',
            'href="/leads"',
            'href="/crm"',
            'href="/crm/inbox"',
            'href="/crm/missed-leads"',
            'href="/crm/handoffs"',
            'href="/crm/campaigns"',
            'href="/analytics"',
            'href="/agent"',
            'href="/admin/security"',
        ):
            assert href in c, href

    def test_active_page_keys_unchanged(self) -> None:
        c = _read("base.html")
        for key in ("dashboard", "crm", "missed_leads", "handoffs", "knowledge", "security"):
            assert f"active_page == '{key}'" in c, key

    def test_lang_is_uzbek(self) -> None:
        assert '<html lang="uz">' in _read("base.html")


# ───────────────────────────── analytics ────────────────────────────────────


class TestAnalyticsUzbek:
    def test_lifecycle_labels_translated(self) -> None:
        c = _read("analytics.html")
        for label in (
            "Jami leadlar",  # Total Leads
            "Manbalar samaradorligi",  # Source Performance
            "Savdo voronkasi",  # Pipeline Funnel
            "Ball taqsimoti",  # Score Distribution
            "Kuzatuv samaradorligi",  # Follow-up Performance
            "Daromad xulosasi",  # Revenue Summary
            "Tavsiyalar",  # Recommendations
        ):
            assert label in c, label

    def test_old_english_lifecycle_removed(self) -> None:
        # the operator-visible (rendered) labels are gone; non-rendered HTML
        # section comments are developer-facing and intentionally left as-is
        c = _read("analytics.html")
        for stale in (
            ">Total Leads</div>",
            ">Source Performance</h2>",
            ">Pipeline Funnel</h2>",
            ">Score Distribution</h2>",
            "No analytics data available",
            "Visual Charts Section",  # the misleading stale comment was removed
        ):
            assert stale not in c, stale

    def test_error_state_distinct_from_empty(self) -> None:
        # an API failure must not read as "no data yet"
        c = _read("analytics.html")
        assert "Tahlil ma'lumotlarini yuklab bo'lmadi" in c
        assert "Hozircha tahlil uchun ma'lumot yo'q" in c
        assert "data._error is defined" in c


class TestAnalyticsTrendRangeToggle:
    def test_toggle_buttons_present(self) -> None:
        c = _read("analytics.html")
        assert "tr-range-btn" in c
        assert 'data-range="today"' in c
        assert 'data-range="7d"' in c
        assert 'data-range="30d"' in c
        assert "Bugun" in c and "7 kun" in c and "30 kun" in c

    def test_fetch_uses_selected_range(self) -> None:
        c = _read("analytics.html")
        assert "function loadTrends(range)" in c
        assert 'summary?range=" + range' in c

    def test_no_token_or_innerhtml_in_trends(self) -> None:
        c = _read("analytics.html")
        assert 'credentials: "same-origin"' in c
        assert "sk-" not in c
        assert ".innerHTML" not in c  # trend bars use createElement/textContent


# ───────────────────────────── missed leads ─────────────────────────────────


class TestMissedLeadsUzbek:
    def test_severity_tiers_translated(self) -> None:
        c = _read("crm_missed_leads.html")
        for label in ("Juda jiddiy", "Yuqori", "O'rta", "Past"):
            assert label in c, label

    def test_internal_severity_values_preserved(self) -> None:
        # filter/badge logic still keys off the reliable lowercase values
        c = _read("crm_missed_leads.html")
        for val in ("'critical'", "'high'", "'medium'", "'low'"):
            assert val in c, val

    def test_phone_masking_preserved(self) -> None:
        assert "phone_masked" in _read("crm_missed_leads.html")

    def test_error_banner_not_all_clear(self) -> None:
        c = _read("crm_missed_leads.html")
        assert "_error" in c
        assert "Ma'lumotlarni yuklab bo'lmadi" in c


# ───────────────────────────── operator pages: no silent failure ────────────


class TestOperatorErrorBanners:
    def test_handoffs_error_banner(self) -> None:
        c = _read("crm_handoffs.html")
        assert "(summary or {})._error or (queue or {})._error" in c
        assert "Ma'lumotlarni yuklab bo'lmadi" in c

    def test_handoffs_labels_translated(self) -> None:
        c = _read("crm_handoffs.html")
        for label in ("Ochiq", "Shoshilinch", "Oddiy"):
            assert label in c, label
        for stale in (">Open<", ">Urgent<", ">Normal<"):
            assert stale not in c, stale

    def test_knowledge_error_banner(self) -> None:
        c = _read("agent_knowledge.html")
        assert "(summary or {})._error or (items or {})._error" in c

    def test_unknown_questions_error_banner(self) -> None:
        c = _read("agent_unknown_questions.html")
        assert "(summary or {})._error or (items or {})._error" in c

    def test_conversations_error_banner(self) -> None:
        c = _read("crm_conversations.html")
        assert "(conversations or {})._error" in c


# ───────────────────────────── no fake stats introduced ─────────────────────


class TestNoFakeStats:
    def test_missed_kpis_bind_to_data(self) -> None:
        # KPI numbers come from the API summary, not hardcoded values
        c = _read("crm_missed_leads.html")
        for expr in ("summary.total", "summary.critical", "summary.high"):
            assert expr in c, expr

    def test_handoff_kpis_bind_to_data(self) -> None:
        c = _read("crm_handoffs.html")
        for expr in ("summary.total_open", "summary.total_urgent", "summary.total_high"):
            assert expr in c, expr


class TestSmoke:
    def test_web_app(self) -> None:
        from apps.web.main import app

        assert app is not None
