"""
Adaptive weights — compute per-tactic weight multipliers from outcome data.

Pure function. Weights are bounded to ±MAX_BOOST (15%).
Tactics with < MIN_SAMPLES are neutral (1.0).

Formula per tactic:
    avg_rate = mean(success_rate) across all tactics in same event_type with ≥ MIN_SAMPLES
    delta = (tactic_rate - avg_rate) / max(avg_rate, 0.01)
    weight = 1.0 + clamp(delta * MAX_BOOST, -MAX_BOOST, +MAX_BOOST)
"""

from __future__ import annotations

from dataclasses import dataclass, field

MIN_SAMPLES = 20
MAX_BOOST = 0.15  # ±15%


@dataclass(frozen=True, slots=True)
class AdaptiveWeights:
    negotiation_weights: dict[str, float] = field(default_factory=dict)
    closer_weights: dict[str, float] = field(default_factory=dict)
    followup_weights: dict[str, float] = field(default_factory=dict)
    data_sufficient: bool = False


def compute_adaptive_weights(resolved_stats: list[dict]) -> AdaptiveWeights:
    """Compute per-tactic weight multipliers from resolved outcome stats."""
    if not resolved_stats:
        return AdaptiveWeights()

    # Group by (event_type, tactic_name) → aggregate success rate
    tactic_rates: dict[tuple[str, str], tuple[float, int]] = {}

    for s in resolved_stats:
        key = (s["event_type"], s["tactic_name"])
        total = s.get("total", 0)
        rate = s.get("success_rate", 0.0)

        if key in tactic_rates:
            prev_rate, prev_total = tactic_rates[key]
            combined_total = prev_total + total
            weighted_rate = (prev_rate * prev_total + rate * total) / max(combined_total, 1)
            tactic_rates[key] = (weighted_rate, combined_total)
        else:
            tactic_rates[key] = (rate, total)

    # Group by event_type
    by_event: dict[str, list[tuple[str, float, int]]] = {}
    for (event_type, tactic_name), (rate, total) in tactic_rates.items():
        by_event.setdefault(event_type, []).append((tactic_name, rate, total))

    # Compute weights per event type
    all_weights: dict[str, dict[str, float]] = {}
    any_sufficient = False

    for event_type, tactics in by_event.items():
        # Only consider tactics with enough samples
        qualified = [(name, rate, total) for name, rate, total in tactics if total >= MIN_SAMPLES]
        if not qualified:
            continue

        any_sufficient = True
        avg_rate = sum(r for _, r, _ in qualified) / len(qualified)

        weights: dict[str, float] = {}
        for name, rate, _ in qualified:
            delta = (rate - avg_rate) / max(avg_rate, 0.01)
            boost = max(-MAX_BOOST, min(delta * MAX_BOOST, MAX_BOOST))
            weights[name] = 1.0 + boost

        all_weights[event_type] = weights

    return AdaptiveWeights(
        negotiation_weights=all_weights.get("negotiation", {}),
        closer_weights=all_weights.get("closer", {}),
        followup_weights=all_weights.get("followup", {}),
        data_sufficient=any_sufficient,
    )
