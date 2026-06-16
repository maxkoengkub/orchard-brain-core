"""Phase 4 — Water Agent.

Specialist agent focused on irrigation adequacy, waterlogging risk, and
Vapor Pressure Deficit (VPD) as an atmospheric drought demand indicator.

Returns an ``AgentAssessment`` following the shared contract in _agent_base.py.
"""
from __future__ import annotations

from ._agent_base import AgentAssessment
from ._thresholds import HUMIDITY, VPD, compute_vpd_kpa
from .orchard_memory import SensorSnapshot, TrendResult
from .knowledge.threshold_engine import ThresholdMap, PARAM_HUMIDITY, PARAM_VPD
from typing import Optional


class WaterAgent:
    """Assess irrigation needs and VPD-driven atmospheric water stress."""

    NAME = "WaterAgent"

    def assess(
        self,
        snapshot: SensorSnapshot,
        trends: list[TrendResult] | None = None,
        thresholds: Optional[ThresholdMap] = None,
    ) -> AgentAssessment:
        trends = trends or []
        sm = snapshot.soil_moisture
        vpd = snapshot.vpd or compute_vpd_kpa(snapshot.temperature, snapshot.humidity)
        T = snapshot.temperature

        risks: list[dict] = []
        recs: list[dict] = []
        
        t_bounds_h = thresholds.get(PARAM_HUMIDITY, {}) if thresholds else {}
        h_crit_hi = t_bounds_h.get("critical_max") or HUMIDITY.critical_high
        h_warn_hi = t_bounds_h.get("warn_max") or HUMIDITY.warn_high
        h_opt_hi = t_bounds_h.get("optimal_max") or HUMIDITY.optimal_high
        h_opt_lo = t_bounds_h.get("optimal_min") or HUMIDITY.optimal_low
        h_warn_lo = t_bounds_h.get("warn_min") or HUMIDITY.warn_low
        h_crit_lo = t_bounds_h.get("critical_min") or HUMIDITY.critical_low

        t_bounds_v = thresholds.get(PARAM_VPD, {}) if thresholds else {}
        v_crit_hi = t_bounds_v.get("critical_max") or VPD.critical_high
        v_warn_hi = t_bounds_v.get("warn_max") or VPD.warn_high
        v_opt_hi = t_bounds_v.get("optimal_max") or VPD.optimal_high

        # ── soil moisture risks
        if sm <= h_crit_lo:
            risks.append({"risk": "drought", "severity": "critical",
                "message": f"Soil moisture {sm:.1f} % is at critical low {h_crit_lo:.0f} % — wilting imminent."})
            recs.append({"action": "trigger_irrigation", "priority": "critical",
                "reason": f"Critical drought: soil moisture {sm:.1f} % must be restored immediately.",
                "confidence": 0.97})
        elif sm <= h_warn_lo:
            risks.append({"risk": "drought", "severity": "warning",
                "message": f"Soil moisture {sm:.1f} % below warning threshold {h_warn_lo:.0f} %."})
            recs.append({"action": "trigger_irrigation", "priority": "high",
                "reason": f"Drought warning: soil moisture {sm:.1f} % needs urgent irrigation.",
                "confidence": 0.85})
        elif sm < h_opt_lo:
            risks.append({"risk": "drought", "severity": "warning",
                "message": f"Soil moisture {sm:.1f} % below optimal minimum {h_opt_lo:.0f} % VWC."})
            recs.append({"action": "trigger_irrigation", "priority": "medium",
                "reason": f"Sub-optimal moisture {sm:.1f} %; schedule a light irrigation cycle.",
                "confidence": 0.68})

        if sm >= h_crit_hi:
            risks.append({"risk": "waterlogging", "severity": "critical",
                "message": f"Soil moisture {sm:.1f} % at critical high — root anaerobia active."})
            recs.append({"action": "stop_irrigation", "priority": "critical",
                "reason": f"Critical waterlogging {sm:.1f} %; stop irrigation and improve drainage.",
                "confidence": 0.96})
        elif sm >= h_warn_hi:
            risks.append({"risk": "waterlogging", "severity": "warning",
                "message": f"Soil moisture {sm:.1f} % exceeds warning high {h_warn_hi:.0f} %."})
            recs.append({"action": "stop_irrigation", "priority": "high",
                "reason": f"Waterlogging warning {sm:.1f} %; stop irrigation and check drainage.",
                "confidence": 0.80})
        elif sm > h_opt_hi:
            risks.append({"risk": "waterlogging", "severity": "warning",
                "message": f"Soil moisture {sm:.1f} % exceeds optimal max {h_opt_hi:.0f} % VWC."})
            recs.append({"action": "stop_irrigation", "priority": "medium",
                "reason": f"Excess moisture {sm:.1f} %; delay next irrigation.",
                "confidence": 0.65})

        # ── VPD risks
        if vpd >= v_crit_hi:
            risks.append({"risk": "vpd_stress", "severity": "critical",
                "message": f"VPD {vpd:.2f} kPa exceeds critical {v_crit_hi:.1f} kPa — stomata closing."})
            recs.append({"action": "trigger_micro_sprinkler_cooling", "priority": "critical",
                "reason": f"Critical VPD {vpd:.2f} kPa; activate misting to lower canopy temperature.",
                "confidence": 0.92})
        elif vpd >= v_warn_hi:
            risks.append({"risk": "vpd_stress", "severity": "warning",
                "message": f"VPD {vpd:.2f} kPa exceeds warning {v_warn_hi:.1f} kPa — evaporative demand high."})
            recs.append({"action": "trigger_micro_sprinkler_cooling", "priority": "high",
                "reason": f"Elevated VPD {vpd:.2f} kPa; start misting to reduce canopy stress.",
                "confidence": 0.78})

        # ── trend-based recommendations
        trend_names = {t.trend for t in trends}
        if "falling_soil_moisture" in trend_names and sm > h_opt_lo:
            recs.append({"action": "increase_irrigation_frequency",
                "priority": "medium",
                "reason": "Soil moisture is trending down — increase irrigation frequency proactively.",
                "confidence": 0.70})
        if "increasing_vpd" in trend_names:
            recs.append({"action": "trigger_micro_sprinkler_cooling",
                "priority": "medium",
                "reason": "VPD is trending upward — prepare cooling measures before stress peaks.",
                "confidence": 0.68})

        status = _status(risks)
        confidence = max((r["confidence"] for r in recs), default=0.0)

        reasoning = (
            f"Soil moisture is {sm:.1f} % (optimal: {h_opt_lo:.0f}–{h_opt_hi:.0f} % VWC). "
            f"VPD is {vpd:.2f} kPa (optimal: <{v_opt_hi:.1f} kPa). "
        )
        if not risks:
            reasoning += "Both irrigation and atmospheric demand are within acceptable limits."
        else:
            reasoning += f"{len(risks)} water-related risk(s) detected: " + ", ".join(r["risk"] for r in risks) + "."

        trend_active = [t.trend for t in trends if t.trend in ("falling_soil_moisture", "increasing_vpd", "prolonged_dry_period")]
        if trend_active:
            reasoning += f" Trends in memory: {', '.join(trend_active)}."

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
