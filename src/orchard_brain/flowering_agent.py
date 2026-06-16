"""Phase 4 — Flowering Agent.

Specialist agent that detects conditions that trigger or impede durian
flowering, based on dry-spell physiology and temperature requirements.

Research basis:
  Eguchi et al. (2024): flowering is initiated ~50 days after a ~15-day
  dry spell (rainfall <1 mm/day; soil moisture consistently below warn_low).
  Cool night temperatures (<22 °C) interfere with fruit set.
"""
from __future__ import annotations

from ._agent_base import AgentAssessment
from ._thresholds import HUMIDITY, TEMPERATURE
from .orchard_memory import SensorSnapshot, TrendResult
from .knowledge.threshold_engine import ThresholdMap, PARAM_TEMPERATURE, PARAM_HUMIDITY
from typing import Optional


class FloweringAgent:
    """Assess flowering trigger conditions and phenological readiness."""

    NAME = "FloweringAgent"

    def assess(
        self,
        snapshot: SensorSnapshot,
        trends: list[TrendResult] | None = None,
        thresholds: Optional[ThresholdMap] = None,
    ) -> AgentAssessment:
        trends = trends or []
        sm = snapshot.soil_moisture
        T = snapshot.temperature
        trend_names = {t.trend for t in trends}

        risks: list[dict] = []
        recs: list[dict] = []

        t_bounds_h = thresholds.get(PARAM_HUMIDITY, {}) if thresholds else {}
        h_warn_lo = t_bounds_h.get("warn_min") or HUMIDITY.warn_low
        h_opt_hi = t_bounds_h.get("optimal_max") or HUMIDITY.optimal_high
        h_warn_hi = t_bounds_h.get("warn_max") or HUMIDITY.warn_high

        t_bounds_t = thresholds.get(PARAM_TEMPERATURE, {}) if thresholds else {}
        t_opt_hi = t_bounds_t.get("optimal_max") or TEMPERATURE.optimal_high
        t_warn_lo = t_bounds_t.get("warn_min") or TEMPERATURE.warn_low

        # ── Prolonged dry spell — flowering trigger window
        prolonged_dry = "prolonged_dry_period" in trend_names
        current_dry = sm < h_warn_lo

        if prolonged_dry and current_dry:
            recs.append({
                "action": "anticipate_flowering_trigger",
                "priority": "medium",
                "reason": (
                    "Sustained dry-spell conditions detected in memory + current reading. "
                    "Flowering initiation may begin in 30-50 days if this persists "
                    "(Eguchi et al., 2024: flowering ~50 days after ~15-day dry spell). "
                    "Schedule bud monitoring; prepare high-K low-N pre-flowering program."
                ),
                "confidence": 0.78,
            })
        elif current_dry and T <= t_opt_hi:
            recs.append({
                "action": "anticipate_flowering_trigger",
                "priority": "low",
                "reason": (
                    f"Dry-spell conditions: soil moisture {sm:.1f} % < {h_warn_lo:.0f} % "
                    f"at T={T:.1f} °C. If sustained for ~15 days, flowering trigger expected. "
                    "Monitor bud development from week 3 onwards."
                ),
                "confidence": 0.65,
            })

        # ── Temperature interference with fruit set
        if T <= t_warn_lo:
            risks.append({
                "risk": "cold_stress",
                "severity": "warning",
                "message": (
                    f"Temperature {T:.1f} °C ≤ {t_warn_lo:.0f} °C — below the minimum "
                    "for healthy fruit set in durian (research: <22 °C impairs pollination)."
                ),
            })
            recs.append({
                "action": "apply_frost_protection",
                "priority": "high",
                "reason": (
                    f"Temperature {T:.1f} °C will interfere with pollen viability "
                    "and fruit set if flowering is imminent."
                ),
                "confidence": 0.75,
            })

        # ── Excess moisture suppresses dry-spell trigger
        if sm >= h_opt_hi and prolonged_dry:
            recs.append({
                "action": "stop_irrigation",
                "priority": "medium",
                "reason": (
                    "Soil moisture is excessive despite a recent dry-spell trend — "
                    "reduce irrigation to maintain the dry-spell needed to trigger flowering."
                ),
                "confidence": 0.70,
            })

        # ── High moisture during flowering — fungal risk
        if sm >= h_warn_hi:
            risks.append({
                "risk": "waterlogging",
                "severity": "warning",
                "message": (
                    f"High soil moisture {sm:.1f} % during potential flowering window — "
                    "wet conditions damage flowers and promote fruit rot."
                ),
            })
            recs.append({
                "action": "stop_irrigation",
                "priority": "high",
                "reason": (
                    "Reduce soil moisture below optimal max to protect flowers "
                    "and prevent fungal fruit rot."
                ),
                "confidence": 0.78,
            })

        status = _status(risks)
        confidence = max((r["confidence"] for r in recs), default=0.0)

        reasoning = (
            f"Soil moisture {sm:.1f} %, temperature {T:.1f} °C. "
        )
        if prolonged_dry:
            reasoning += "Memory shows a prolonged dry period — flowering trigger conditions are active. "
        if current_dry and not prolonged_dry:
            reasoning += "Current dry conditions may begin a dry-spell flowering trigger if sustained. "
        if not risks and not recs:
            reasoning += (
                "No immediate flowering trigger or interference detected. "
                "Conditions are adequate for vegetative growth."
            )
        elif recs:
            reasoning += f"{len(recs)} recommendation(s) issued by the flowering module."

        return AgentAssessment(
            agent=self.NAME,
            status=status,
            risks=risks,
            recommendations=recs,
            confidence=round(confidence, 2),
            reasoning=reasoning,
        )


def _status(risks: list[dict]) -> str:
    if any(r["severity"] == "critical" for r in risks):
        return "critical"
    if any(r["severity"] == "warning" for r in risks):
        return "warning"
    return "ok"
