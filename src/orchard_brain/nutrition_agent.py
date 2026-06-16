"""Phase 4 — Nutrition Agent.

Specialist agent focused on soil pH and electrical conductivity (EC)
as proxies for nutrient availability and fertigation balance.
"""
from __future__ import annotations

from ._agent_base import AgentAssessment
from ._thresholds import EC, PH
from .orchard_memory import SensorSnapshot, TrendResult
from .knowledge.threshold_engine import ThresholdMap, PARAM_PH, PARAM_EC
from typing import Optional


class NutritionAgent:
    """Assess pH and EC for nutrient stress and fertigation balance."""

    NAME = "NutritionAgent"

    def assess(
        self,
        snapshot: SensorSnapshot,
        trends: list[TrendResult] | None = None,
        thresholds: Optional[ThresholdMap] = None,
    ) -> AgentAssessment:
        trends = trends or []
        ph = snapshot.ph
        ec = snapshot.ec

        risks: list[dict] = []
        recs: list[dict] = []
        
        t_bounds_ph = thresholds.get(PARAM_PH, {}) if thresholds else {}
        ph_crit_hi = t_bounds_ph.get("critical_max") or PH.critical_high
        ph_warn_hi = t_bounds_ph.get("warn_max") or PH.warn_high
        ph_opt_hi = t_bounds_ph.get("optimal_max") or PH.optimal_high
        ph_opt_lo = t_bounds_ph.get("optimal_min") or PH.optimal_low
        ph_warn_lo = t_bounds_ph.get("warn_min") or PH.warn_low
        ph_crit_lo = t_bounds_ph.get("critical_min") or PH.critical_low

        t_bounds_ec = thresholds.get(PARAM_EC, {}) if thresholds else {}
        ec_crit_hi = t_bounds_ec.get("critical_max") or EC.critical_high
        ec_warn_hi = t_bounds_ec.get("warn_max") or EC.warn_high
        ec_opt_hi = t_bounds_ec.get("optimal_max") or EC.optimal_high
        ec_opt_lo = t_bounds_ec.get("optimal_min") or EC.optimal_low
        ec_warn_lo = t_bounds_ec.get("warn_min") or EC.warn_low
        ec_crit_lo = t_bounds_ec.get("critical_min") or EC.critical_low

        # ── pH risks (research: optimal 5.5-6.5; Ngoc et al., 2024)
        if ph <= ph_crit_lo:
            risks.append({"risk": "ph_acid", "severity": "critical",
                "message": f"pH {ph:.2f} ≤ critical low {ph_crit_lo:.1f} — toxic acidity."})
            recs.append({"action": "apply_lime_to_raise_ph", "priority": "critical",
                "reason": "Apply agricultural lime immediately to prevent Ca/Mg/P lock-out.",
                "confidence": _conf(ph, ph_warn_lo, ph_crit_lo)})
        elif ph <= ph_warn_lo:
            risks.append({"risk": "ph_acid", "severity": "warning",
                "message": f"pH {ph:.2f} below warning {ph_warn_lo:.1f}."})
            recs.append({"action": "apply_lime_to_raise_ph", "priority": "high",
                "reason": f"pH {ph:.2f} below safe range; apply lime to return to 5.5-6.5.",
                "confidence": _conf(ph, ph_warn_lo, ph_crit_lo)})
        elif ph < ph_opt_lo:
            risks.append({"risk": "ph_acid", "severity": "warning",
                "message": f"pH {ph:.2f} below optimal minimum {ph_opt_lo:.1f}."})
            recs.append({"action": "apply_lime_to_raise_ph", "priority": "medium",
                "reason": f"pH {ph:.2f} is mildly acidic; schedule lime application.",
                "confidence": 0.62})

        if ph >= ph_crit_hi:
            risks.append({"risk": "ph_alkaline", "severity": "critical",
                "message": f"pH {ph:.2f} ≥ critical high {ph_crit_hi:.1f} — micronutrient lock-out."})
            recs.append({"action": "apply_sulfur_to_lower_ph", "priority": "critical",
                "reason": "Apply elemental sulfur urgently — Fe/Zn/Mn completely unavailable.",
                "confidence": _conf(ph, ph_warn_hi, ph_crit_hi)})
        elif ph >= ph_warn_hi:
            risks.append({"risk": "ph_alkaline", "severity": "warning",
                "message": f"pH {ph:.2f} above warning high {ph_warn_hi:.1f} (optimal ≤6.5)."})
            recs.append({"action": "apply_sulfur_to_lower_ph", "priority": "high",
                "reason": f"pH {ph:.2f} exceeds optimal; apply acidifier to return to 5.5-6.5.",
                "confidence": _conf(ph, ph_warn_hi, ph_crit_hi)})
        elif ph > ph_opt_hi:
            risks.append({"risk": "ph_alkaline", "severity": "warning",
                "message": f"pH {ph:.2f} slightly above optimal {ph_opt_hi:.1f}."})
            recs.append({"action": "apply_sulfur_to_lower_ph", "priority": "medium",
                "reason": f"pH {ph:.2f} is drifting alkaline; monitor and plan acidification.",
                "confidence": 0.62})

        # ── EC risks
        if ec <= ec_crit_lo:
            risks.append({"risk": "nutrient_deficiency", "severity": "critical",
                "message": f"EC {ec:.0f} µS/cm ≤ critical low {ec_crit_lo:.0f} — severe starvation."})
            recs.append({"action": "adjust_fertigation_ratio_to_high_pk", "priority": "critical",
                "reason": "Apply high-PK fertigation immediately (Tang et al., 2024).",
                "confidence": _conf(ec, ec_warn_lo, ec_crit_lo)})
        elif ec <= ec_warn_lo:
            risks.append({"risk": "nutrient_deficiency", "severity": "warning",
                "message": f"EC {ec:.0f} µS/cm below warning {ec_warn_lo:.0f}."})
            recs.append({"action": "adjust_fertigation_ratio_to_high_pk", "priority": "high",
                "reason": f"EC {ec:.0f} µS/cm indicates dilute nutrient solution; increase fertigation.",
                "confidence": _conf(ec, ec_warn_lo, ec_crit_lo)})
        elif ec < ec_opt_lo:
            risks.append({"risk": "nutrient_deficiency", "severity": "warning",
                "message": f"EC {ec:.0f} µS/cm below optimal {ec_opt_lo:.0f}."})
            recs.append({"action": "adjust_fertigation_ratio_to_high_pk", "priority": "medium",
                "reason": f"EC {ec:.0f} µS/cm is sub-optimal; light fertigation boost recommended.",
                "confidence": 0.62})

        if ec >= ec_crit_hi:
            risks.append({"risk": "nutrient_toxicity", "severity": "critical",
                "message": f"EC {ec:.0f} µS/cm ≥ critical high {ec_crit_hi:.0f} — root burn."})
            recs.append({"action": "flush_irrigation_to_reduce_ec", "priority": "critical",
                "reason": "Flush root zone with clean water immediately to prevent salt toxicity.",
                "confidence": _conf(ec, ec_warn_hi, ec_crit_hi)})
        elif ec >= ec_warn_hi:
            risks.append({"risk": "nutrient_toxicity", "severity": "warning",
                "message": f"EC {ec:.0f} µS/cm exceeds warning {ec_warn_hi:.0f}."})
            recs.append({"action": "flush_irrigation_to_reduce_ec", "priority": "high",
                "reason": f"EC {ec:.0f} µS/cm is elevated; leaching irrigation cycle needed.",
                "confidence": _conf(ec, ec_warn_hi, ec_crit_hi)})
        elif ec > ec_opt_hi:
            risks.append({"risk": "nutrient_toxicity", "severity": "warning",
                "message": f"EC {ec:.0f} µS/cm slightly above optimal {ec_opt_hi:.0f}."})
            recs.append({"action": "flush_irrigation_to_reduce_ec", "priority": "low",
                "reason": f"EC {ec:.0f} µS/cm is slightly high; reduce fertigation concentration.",
                "confidence": 0.62})

        status = _status(risks)
        confidence = max((r["confidence"] for r in recs), default=0.0)

        reasoning = (
            f"Soil pH is {ph:.2f} (optimal: {ph_opt_lo:.1f}-{ph_opt_hi:.1f}). "
            f"Fertigation EC is {ec:.0f} µS/cm (optimal: {ec_opt_lo:.0f}-{ec_opt_hi:.0f} µS/cm). "
        )
        reasoning += (
            "All nutrient parameters are within optimal ranges — no adjustments needed."
            if not risks else
            f"{len(risks)} nutrient risk(s) detected: " + ", ".join(r["risk"] for r in risks) + "."
        )

        return AgentAssessment(
            agent=self.NAME,
            status=status,
            risks=risks,
            recommendations=recs,
            confidence=round(confidence, 2),
            reasoning=reasoning,
        )


def _conf(value: float, warn: float, critical: float) -> float:
    span = abs(critical - warn)
    if span < 1e-9:
        return 0.80
    ratio = min(1.0, abs(value - warn) / span)
    return round(0.60 + ratio * 0.37, 2)


def _status(risks: list[dict]) -> str:
    if any(r["severity"] == "critical" for r in risks):
        return "critical"
    if any(r["severity"] == "warning" for r in risks):
        return "warning"
    return "ok"
