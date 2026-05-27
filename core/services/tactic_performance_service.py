"""
Tactic performance analytics — aggregates resolved outcome stats into per-tactic performance.

Pure function, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TacticPerformance:
    tactic_name: str
    event_type: str
    total_samples: int
    success_rate: float  # (engaged + measurement_booked + converted) / total
    engaged_rate: float
    conversion_rate: float
    lost_rate: float
    ignored_rate: float
    by_segment: dict[str, float] = field(default_factory=dict)  # hot/warm/cold → success_rate


@dataclass(frozen=True, slots=True)
class TacticPerformanceReport:
    tactics: list[TacticPerformance]
    best_negotiation_tactic: str | None
    worst_negotiation_tactic: str | None
    best_closer_action: str | None
    best_followup_type: str | None
    total_tracked: int
    total_resolved: int


def build_tactic_performance(resolved_stats: list[dict]) -> TacticPerformanceReport:
    """Build performance report from resolved stats (output of repo.get_resolved_stats())."""
    if not resolved_stats:
        return TacticPerformanceReport(
            tactics=[],
            best_negotiation_tactic=None,
            worst_negotiation_tactic=None,
            best_closer_action=None,
            best_followup_type=None,
            total_tracked=0,
            total_resolved=0,
        )

    # Group stats by (event_type, tactic_name) — segment rows get merged
    grouped: dict[tuple[str, str], dict] = {}
    total_tracked = 0
    total_resolved = 0

    for s in resolved_stats:
        key = (s["event_type"], s["tactic_name"])
        total = s.get("total", 0)
        total_tracked += total
        total_resolved += total

        if key not in grouped:
            grouped[key] = {
                "engaged": 0,
                "measurement_booked": 0,
                "converted": 0,
                "lost": 0,
                "ignored": 0,
                "total": 0,
                "by_segment": {},
            }

        g = grouped[key]
        g["engaged"] += s.get("engaged", 0)
        g["measurement_booked"] += s.get("measurement_booked", 0)
        g["converted"] += s.get("converted", 0)
        g["lost"] += s.get("lost", 0)
        g["ignored"] += s.get("ignored", 0)
        g["total"] += total

        # Track per-segment success rate
        segment = s.get("segment")
        if segment:
            g["by_segment"][segment] = s.get("success_rate", 0.0)

    # Build TacticPerformance objects
    tactics: list[TacticPerformance] = []
    for (event_type, tactic_name), g in grouped.items():
        t = g["total"] or 1
        success = g["engaged"] + g["measurement_booked"] + g["converted"]
        tactics.append(
            TacticPerformance(
                tactic_name=tactic_name,
                event_type=event_type,
                total_samples=g["total"],
                success_rate=success / t,
                engaged_rate=g["engaged"] / t,
                conversion_rate=g["converted"] / t,
                lost_rate=g["lost"] / t,
                ignored_rate=g["ignored"] / t,
                by_segment=g["by_segment"],
            )
        )

    # Find best/worst per event type
    def _best(et: str) -> str | None:
        candidates = [t for t in tactics if t.event_type == et and t.total_samples >= 5]
        return max(candidates, key=lambda x: x.success_rate).tactic_name if candidates else None

    def _worst(et: str) -> str | None:
        candidates = [t for t in tactics if t.event_type == et and t.total_samples >= 5]
        return min(candidates, key=lambda x: x.success_rate).tactic_name if candidates else None

    return TacticPerformanceReport(
        tactics=sorted(tactics, key=lambda x: x.success_rate, reverse=True),
        best_negotiation_tactic=_best("negotiation"),
        worst_negotiation_tactic=_worst("negotiation"),
        best_closer_action=_best("closer"),
        best_followup_type=_best("followup"),
        total_tracked=total_tracked,
        total_resolved=total_resolved,
    )
