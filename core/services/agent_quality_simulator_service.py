"""Deterministic agent quality simulator — no external API calls."""
from __future__ import annotations

import re

from core.schemas.agent_quality_simulator import (
    AgentQualityReport,
    AgentScenario,
    AgentScenarioResult,
)

_TOKEN_RE = re.compile(r"sk-[a-zA-Z0-9]{8,}", re.I)
_FORBIDDEN_CLAIMS = frozenset({
    "eng arzon",
    "aniq narx",
    "final narx",
    "bugun qilamiz",
    "bugun kelamiz",
    "bugun keladi",
    "hozir qo'ng'iroq",
    "hozir darhol",
    "100% kafolat",
    "100% chegirma",
    "yozib qo'ydim",
    "usta boradi",
    "maxsus chegirma",
})


class AgentQualitySimulatorService:

    def run_scenario(self, scenario: AgentScenario) -> AgentScenarioResult:
        from apps.bot.handlers.private.ai_detection import (
            _is_catalog_request,
            _is_greeting,
            _is_measurement_request,
            _is_price_query,
        )
        from apps.bot.handlers.private.ai_scoring import (
            detect_objection_full,
        )
        from core.services.price_calculator_service import (
            PriceCalculatorService,
        )

        text = scenario.text
        result = AgentScenarioResult(scenario=scenario)

        result.is_price_query = _is_price_query(text)
        result.is_catalog_request = _is_catalog_request(text)
        result.is_measurement_request = _is_measurement_request(text)
        result.is_greeting = _is_greeting(text)

        try:
            from core.services.followup_scheduler_service import _STOP_WORDS

            result.is_stop_signal = text.lower().strip() in _STOP_WORDS
        except Exception:
            pass

        obj = detect_objection_full(text)
        if obj:
            result.objection_type = obj.objection_type
            result.objection_severity = obj.severity

        calc = PriceCalculatorService()
        result.area_parsed = calc.parse_area_from_text(text)
        result.design_parsed = calc.parse_design_from_text(text)

        if result.area_parsed and result.design_parsed:
            est = calc.calculate_estimate(result.area_parsed, result.design_parsed)
            result.price_estimate_total = est.total_uzs
        elif result.area_parsed and not result.design_parsed:
            result.clarification_needed = "design"
        elif result.design_parsed and not result.area_parsed:
            result.clarification_needed = "area"

        if result.is_price_query:
            result.detected_intent = "wants_price"
        elif result.objection_type:
            result.detected_intent = f"objection_{result.objection_type}"
        elif result.is_catalog_request:
            result.detected_intent = "wants_catalog"
        elif result.is_measurement_request:
            result.detected_intent = "wants_measurement"
        elif result.is_stop_signal:
            result.detected_intent = "stop_request"
        elif result.is_greeting:
            result.detected_intent = "greeting"
        elif "operator" in text.lower() or "odam" in text.lower():
            result.detected_intent = "wants_operator"
        else:
            result.detected_intent = "other"

        result.safety_violations = self.detect_safety_violations(text)
        result.safety_status = "violation" if result.safety_violations else "safe"
        result.score = self._score_result(result)

        return result

    def detect_safety_violations(self, text: str) -> list[str]:
        violations = []
        lower = text.lower()
        for claim in _FORBIDDEN_CLAIMS:
            if claim in lower:
                violations.append(f"forbidden_claim:{claim}")
        if _TOKEN_RE.search(text):
            violations.append("token_leak")
        return violations

    def run_suite(
        self, scenarios: list[AgentScenario],
    ) -> list[AgentScenarioResult]:
        return [self.run_scenario(s) for s in scenarios]

    def build_quality_report(
        self, results: list[AgentScenarioResult],
    ) -> AgentQualityReport:
        if not results:
            return AgentQualityReport()

        total = len(results)
        passed = sum(1 for r in results if r.score >= 3)
        failed = total - passed
        avg = sum(r.score for r in results) / total
        violations = sum(1 for r in results if r.safety_violations)

        cat_scores: dict[str, list[int]] = {}
        failed_list: list[str] = []
        for r in results:
            cat = r.scenario.category
            cat_scores.setdefault(cat, []).append(r.score)
            if r.score < 3:
                failed_list.append(
                    f"{r.scenario.text} ({r.scenario.category}): {r.score}/5",
                )

        cat_avg = {
            k: sum(v) / len(v) for k, v in cat_scores.items()
        }

        return AgentQualityReport(
            total_scenarios=total,
            total_passed=passed,
            total_failed=failed,
            avg_score=round(avg, 2),
            safety_violations=violations,
            category_scores=cat_avg,
            failed_scenarios=failed_list,
        )

    @staticmethod
    def _score_result(result: AgentScenarioResult) -> int:
        score = 3
        if result.detected_intent and result.detected_intent != "other":
            score += 1
        if result.price_estimate_total and result.price_estimate_total > 0:
            score += 1
        if result.safety_violations:
            score -= 2
        if result.is_stop_signal and result.detected_intent == "stop_request":
            score = max(score, 4)
        return max(1, min(5, score))
