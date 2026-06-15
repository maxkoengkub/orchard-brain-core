"""Phase 4 — Nutrition Agent.

Specialist agent focused on soil pH and electrical conductivity (EC)
as proxies for nutrient availability and fertigation balance.
"""
from __future__ import annotations

from ._agent_base import AgentAssessment, RecommendationDict, RiskDict
from ._thresholds import EC, PH
from .orchard_memory import SensorSnapshot, TrendResult


class NutritionAgent:
    """Assess pH and EC for nutrient stress and fertigation balance."""

    NAME = "NutritionAgent"

    def assess(
        self,
        snapshot: SensorSnapshot,
        trends: list[TrendResult] | None = None,
    ) -> AgentAssessment:
        trends = trends or []
        ph = snapshot.ph
        ec = snapshot.ec

        risks: list[RiskDict] = []
        recs: list[RecommendationDict] = []

        # ── pH risks (research: optimal 5.5-6.5; Ngoc et al., 2024)
        if ph <= PH.critical_low:
            risks.append({"risk": "ph_acid", "severity": "critical",
                "message": f"pH {ph:.2f} ≤ critical low {PH.critical_low:.1f} — toxic acidity."})
            recs.append({"action": "apply_lime_to_raise_ph", "priority": "critical",
                "reason": "Apply agricultural lime immediately to prevent Ca/Mg/P lock-out.",
                "confidence": _conf(ph, PH.warn_low, PH.critical_low)})
        elif ph <= PH.warn_low:
            risks.append({"risk": "ph_acid", "severity": "warning",
                "message": f"pH {ph:.2f} below warning {PH.warn_low:.1f}."})
            recs.append({"action": "apply_lime_to_raise_ph", "priority": "high",
                "reason": f"pH {ph:.2f} below safe range; apply lime to return to 5.5-6.5.",
                "confidence": _conf(ph, PH.warn_low, PH.critical_low)})
        elif ph < PH.optimal_low:
            risks.append({"risk": "ph_acid", "severity": "warning",
                "message": f"pH {ph:.2f} below optimal minimum {PH.optimal_low:.1f}."})
            recs.append({"action": "apply_lime_to_raise_ph", "priority": "medium",
                "reason": f"pH {ph:.2f} is mildly acidic; schedule lime application.",
                "confidence": 0.62})

        if ph >= PH.critical_high:
            risks.append({"risk": "ph_alkaline", "severity": "critical",
                "message": f"pH {ph:.2f} ≥ critical high {PH.critical_high:.1f} — micronutrient lock-out."})
            recs.append({"action": "apply_sulfur_to_lower_ph", "priority": "critical",
                "reason": "Apply elemental sulfur urgently — Fe/Zn/Mn completely unavailable.",
                "confidence": _conf(ph, PH.warn_high, PH.critical_high)})
        elif ph >= PH.warn_high:
            risks.append({"risk": "ph_alkaline", "severity": "warning",
                "message": f"pH {ph:.2f} above warning high {PH.warn_high:.1f} (optimal ≤6.5)."})
            recs.append({"action": "apply_sulfur_to_lower_ph", "priority": "high",
                "reason": f"pH {ph:.2f} exceeds optimal; apply acidifier to return to 5.5-6.5.",
                "confidence": _conf(ph, PH.warn_high, PH.critical_high)})
        elif ph > PH.optimal_high:
            risks.append({"risk": "ph_alkaline", "severity": "warning",
                "message": f"pH {ph:.2f} slightly above optimal {PH.optimal_high:.1f}."})
            recs.append({"action": "apply_sulfur_to_lower_ph", "priority": "medium",
                "reason": f"pH {ph:.2f} is drifting alkaline; monitor and plan acidification.",
                "confidence": 0.62})

        # ── EC risks
        if ec <= EC.critical_low:
            risks.append({"risk": "nutrient_deficiency", "severity": "critical",
                "message": f"EC {ec:.0f} µS/cm ≤ critical low {EC.critical_low:.0f} — severe starvation."})
            recs.append({"action": "adjust_fertigation_ratio_to_high_pk", "priority": "critical",
                "reason": "Apply high-PK fertigation immediately (Tang et al., 2024).",
                "confidence": _conf(ec, EC.warn_low, EC.critical_low)})
        elif ec <= EC.warn_low:
            risks.append({"risk": "nutrient_deficiency", "severity": "warning",
                "message": f"EC {ec:.0f} µS/cm below warning {EC.warn_low:.0f}."})
            recs.append({"action": "adjust_fertigation_ratio_to_high_pk", "priority": "high",
                "reason": f"EC {ec:.0f} µS/cm indicates dilute nutrient solution; increase fertigation.",
                "confidence": _conf(ec, EC.warn_low, EC.critical_low)})
        elif ec < EC.optimal_low:
            risks.append({"risk": "nutrient_deficiency", "severity": "warning",
                "message": f"EC {ec:.0f} µS/cm below optimal {EC.optimal_low:.0f}."})
            recs.append({"action": "adjust_fertigation_ratio_to_high_pk", "priority": "medium",
                "reason": f"EC {ec:.0f} µS/cm is sub-optimal; light fertigation boost recommended.",
                "confidence": 0.62})

        if ec >= EC.critical_high:
            risks.append({"risk": "nutrient_toxicity", "severity": "critical",
                "message": f"EC {ec:.0f} µS/cm ≥ critical high {EC.critical_high:.0f} — root burn."})
            recs.append({"action": "flush_irrigation_to_reduce_ec", "priority": "critical",
                "reason": "Flush root zone with clean water immediately to prevent salt toxicity.",
                "confidence": _conf(ec, EC.warn_high, EC.critical_high)})
        elif ec >= EC.warn_high:
            risks.append({"risk": "nutrient_toxicity", "severity": "warning",
                "message": f"EC {ec:.0f} µS/cm exceeds warning {EC.warn_high:.0f}."})
            recs.append({"action": "flush_irrigation_to_reduce_ec", "priority": "high",
                "reason": f"EC {ec:.0f} µS/cm is elevated; leaching irrigation cycle needed.",
                "confidence": _conf(ec, EC.warn_high, EC.critical_high)})
        elif ec > EC.optimal_high:
            risks.append({"risk": "nutrient_toxicity", "severity": "warning",
                "message": f"EC {ec:.0f} µS/cm slightly above optimal {EC.optimal_high:.0f}."})
            recs.append({"action": "flush_irrigation_to_reduce_ec", "priority": "low",
                "reason": f"EC {ec:.0f} µS/cm is slightly high; reduce fertigation concentration.",
                "confidence": 0.62})

        status = _status(risks)
        confidence = max((r["confidence"] for r in recs), default=0.0)

        reasoning = (
            f"Soil pH is {ph:.2f} (optimal: {PH.optimal_low:.1f}-{PH.optimal_high:.1f}). "
            f"Fertigation EC is {ec:.0f} µS/cm (optimal: {EC.optimal_low:.0f}-{EC.optimal_high:.0f} µS/cm). "
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


def _status(risks: list[RiskDict]) -> str:
    if any(r["severity"] == "critical" for r in risks):
        return "critical"
    if any(r["severity"] == "warning" for r in risks):
        return "warning"
    return "ok"
