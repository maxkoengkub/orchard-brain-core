"""Phase 4 — Disease Agent.

Specialist agent focused on Phytophthora palmivora disease risk.
Assesses the temperature × soil moisture environment and returns
structured risks and recommendations with confidence scores.
"""
from __future__ import annotations

from ._agent_base import AgentAssessment
from ._thresholds import HUMIDITY, PHYTOPHTHORA
from .orchard_memory import SensorSnapshot, TrendResult


class DiseaseAgent:
    """Assess Phytophthora palmivora infection risk."""

    NAME = "DiseaseAgent"

    def assess(
        self,
        snapshot: SensorSnapshot,
        trends: list[TrendResult] | None = None,
    ) -> AgentAssessment:
        trends = trends or []
        T = snapshot.temperature
        sm = snapshot.soil_moisture

        risks: list[dict] = []
        recs: list[dict] = []

        temp_in_range = PHYTOPHTHORA.temp_favour_low <= T <= PHYTOPHTHORA.temp_favour_high
        wet_period = any(t.trend == "excessive_wet_period" for t in trends)

        if temp_in_range and sm >= PHYTOPHTHORA.moisture_critical:
            conf = min(0.97, 0.60 + (sm - PHYTOPHTHORA.moisture_warn) /
                       (PHYTOPHTHORA.moisture_critical - PHYTOPHTHORA.moisture_warn) * 0.37)
            risks.append({"risk": "phytophthora_risk", "severity": "critical",
                "message": (
                    f"Critical P. palmivora risk: T={T:.1f} °C in pathogen range and "
                    f"soil moisture {sm:.1f} % ≥ {PHYTOPHTHORA.moisture_critical:.0f} %."
                )})
            recs.append({"action": "inspect_for_phytophthora", "priority": "critical",
                "reason": (
                    "Inspect all trees for root/stem canker and apply phosphonate fungicide "
                    "(Guest & Drenth, 2004)."
                ), "confidence": round(conf, 2)})
            recs.append({"action": "apply_mulch_for_disease_prevention", "priority": "high",
                "reason": "Apply 10-15 cm organic mulch to reduce soil splash and improve drainage.",
                "confidence": round(conf * 0.90, 2)})

        elif temp_in_range and sm >= PHYTOPHTHORA.moisture_warn:
            conf = min(0.80, 0.60 + (sm - PHYTOPHTHORA.moisture_warn) /
                       (PHYTOPHTHORA.moisture_critical - PHYTOPHTHORA.moisture_warn) * 0.20)
            risks.append({"risk": "phytophthora_risk", "severity": "warning",
                "message": (
                    f"P. palmivora-favourable conditions: T={T:.1f} °C + soil moisture {sm:.1f} %."
                )})
            recs.append({"action": "apply_mulch_for_disease_prevention", "priority": "medium",
                "reason": "Apply mulch and improve drainage to reduce Phytophthora infection risk.",
                "confidence": round(conf, 2)})

        if wet_period and not risks:
            risks.append({"risk": "phytophthora_risk", "severity": "warning",
                "message": "Extended wet period in sensor memory raises Phytophthora risk."})
            recs.append({"action": "apply_mulch_for_disease_prevention", "priority": "medium",
                "reason": "Memory shows sustained wet conditions — preventive mulch recommended.",
                "confidence": 0.70})

        status = _status(risks)
        confidence = max((r["confidence"] for r in recs), default=0.0)

        if not risks:
            reasoning = (
                f"T={T:.1f} °C, soil moisture={sm:.1f} %. "
                f"Conditions are outside the critical Phytophthora window "
                f"({PHYTOPHTHORA.temp_favour_low:.0f}–{PHYTOPHTHORA.temp_favour_high:.0f} °C × "
                f"≥{PHYTOPHTHORA.moisture_warn:.0f} % VWC). Disease risk is low."
            )
        else:
            reasoning = (
                f"T={T:.1f} °C and soil moisture={sm:.1f} % fall within or near "
                f"the conditions that favour P. palmivora sporulation. "
                f"Disease risk is {status}. "
                f"Mulching, improved drainage, and phosphonate application are indicated."
            )

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
