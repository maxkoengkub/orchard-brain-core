"""Phase 4 — Yield Agent.

Specialist agent that predicts yield productivity potential based on the
integrated state of all key agronomic variables.  Rule-based: no ML.

Yield potential is rated on a 0-100 index derived from:
  - Temperature suitability  (25%)
  - Water/moisture adequacy  (35%)
  - Nutrient balance (EC/pH) (25%)
  - Disease pressure absence (15%)
"""
from __future__ import annotations

from typing import Optional

from ._agent_base import AgentAssessment
from ._thresholds import EC, HUMIDITY, PH, PHYTOPHTHORA, TEMPERATURE, VPD, compute_vpd_kpa
from .orchard_memory import SensorSnapshot, TrendResult
from .knowledge.threshold_engine import (
    ThresholdMap,
    PARAM_TEMPERATURE,
    PARAM_HUMIDITY,
    PARAM_EC,
    PARAM_PH,
    PARAM_VPD,
    PARAM_PHYTOPHTHORA
)


class YieldAgent:
    """Predict yield potential and identify productivity-limiting factors."""

    NAME = "YieldAgent"

    # Weights (must sum to 1.0)
    _W_TEMP = 0.25
    _W_WATER = 0.35
    _W_NUTRIENT = 0.25
    _W_DISEASE = 0.15

    def assess(
        self,
        snapshot: SensorSnapshot,
        trends: list[TrendResult] | None = None,
        thresholds: Optional[ThresholdMap] = None,
    ) -> AgentAssessment:
        trends = trends or []
        T = snapshot.temperature
        sm = snapshot.soil_moisture
        ph = snapshot.ph
        ec = snapshot.ec
        vpd = snapshot.vpd or compute_vpd_kpa(T, snapshot.humidity)

        # ── component scores (0–100)
        temp_score = self._temperature_score(T, thresholds)
        water_score = self._water_score(sm, vpd, thresholds)
        nutrient_score = self._nutrient_score(ec, ph, thresholds)
        disease_score = self._disease_score(T, sm, thresholds)

        yield_potential = round(
            temp_score    * self._W_TEMP
            + water_score * self._W_WATER
            + nutrient_score * self._W_NUTRIENT
            + disease_score  * self._W_DISEASE
        )

        risks: list[dict] = []
        recs: list[dict] = []

        # Limiting factors
        limiting = self._find_limiting_factors(
            temp_score, water_score, nutrient_score, disease_score
        )

        if yield_potential < 40:
            risks.append({"risk": "low_yield_potential", "severity": "critical",
                "message": (
                    f"Yield potential index is {yield_potential}/100 — critical. "
                    f"Limiting factors: {', '.join(limiting)}."
                )})
            recs.append({"action": "urgent_multi_factor_correction", "priority": "critical",
                "reason": (
                    f"Multiple factors are suppressing yield: {', '.join(limiting)}. "
                    "Address each in priority order immediately."
                ),
                "confidence": 0.85})
        elif yield_potential < 65:
            risks.append({"risk": "reduced_yield_potential", "severity": "warning",
                "message": (
                    f"Yield potential index is {yield_potential}/100 — below target. "
                    f"Limiting factors: {', '.join(limiting)}."
                )})
            if limiting:
                recs.append({"action": "optimise_limiting_factor",
                    "priority": "high",
                    "reason": (
                        f"Primary yield constraint is: {limiting[0]}. "
                        "Resolve this factor first for greatest productivity gain."
                    ),
                    "confidence": 0.75})
        elif yield_potential >= 85:
            recs.append({"action": "maintain_current_conditions", "priority": "low",
                "reason": (
                    f"Yield potential index {yield_potential}/100 is excellent. "
                    "Maintain current management practices."
                ),
                "confidence": 0.90})

        # Trend-based yield risks
        trend_names = {t.trend for t in trends}
        if "falling_soil_moisture" in trend_names:
            risks.append({"risk": "trending_yield_reduction", "severity": "warning",
                "message": "Declining soil moisture trend will reduce yield potential if uncorrected."})
            recs.append({"action": "trigger_irrigation", "priority": "medium",
                "reason": "Soil moisture trend is downward — irrigate proactively to protect yield.",
                "confidence": 0.72})

        status = _status(risks)
        confidence = max((r["confidence"] for r in recs), default=0.50)

        reasoning = (
            f"Yield potential index: {yield_potential}/100. "
            f"Component scores — Temperature: {temp_score:.0f}/100, "
            f"Water: {water_score:.0f}/100, Nutrient: {nutrient_score:.0f}/100, "
            f"Disease pressure: {disease_score:.0f}/100. "
        )
        if limiting:
            reasoning += f"Primary limiting factor(s): {', '.join(limiting[:2])}. "
        else:
            reasoning += "All components are performing optimally. "

        return AgentAssessment(
            agent=self.NAME,
            status=status,
            risks=risks,
            recommendations=recs,
            confidence=round(confidence, 2),
            reasoning=reasoning,
        )

    # ──────────────────────────────────────── component scorers

    def _temperature_score(self, T: float, thresholds: Optional[ThresholdMap] = None) -> float:
        t_bounds = thresholds.get(PARAM_TEMPERATURE, {}) if thresholds else {}
        opt_lo = t_bounds.get("optimal_min") or TEMPERATURE.optimal_low
        opt_hi = t_bounds.get("optimal_max") or TEMPERATURE.optimal_high

        if opt_lo <= T <= opt_hi:
            return 100.0
        if T < opt_lo:
            return max(0.0, 100.0 - (opt_lo - T) * 8.0)
        return max(0.0, 100.0 - (T - opt_hi) * 12.0)

    def _water_score(self, sm: float, vpd: float, thresholds: Optional[ThresholdMap] = None) -> float:
        t_bounds_h = thresholds.get(PARAM_HUMIDITY, {}) if thresholds else {}
        opt_lo = t_bounds_h.get("optimal_min") or HUMIDITY.optimal_low
        opt_hi = t_bounds_h.get("optimal_max") or HUMIDITY.optimal_high

        t_bounds_v = thresholds.get(PARAM_VPD, {}) if thresholds else {}
        v_crit_hi = t_bounds_v.get("critical_max") or VPD.critical_high
        v_warn_hi = t_bounds_v.get("warn_max") or VPD.warn_high

        if opt_lo <= sm <= opt_hi:
            base = 100.0
        elif sm < opt_lo:
            base = max(0.0, 100.0 - (opt_lo - sm) / opt_lo * 100.0)
        else:
            base = max(0.0, 100.0 - (sm - opt_hi) / (100.0 - opt_hi) * 100.0)
        # VPD penalty (compare kPa against VPD thresholds, not temperature thresholds)
        if vpd >= v_crit_hi:
            base *= 0.5
        elif vpd >= v_warn_hi:
            base *= 0.75
        return base

    def _nutrient_score(self, ec: float, ph: float, thresholds: Optional[ThresholdMap] = None) -> float:
        t_bounds_ec = thresholds.get(PARAM_EC, {}) if thresholds else {}
        ec_opt_lo = t_bounds_ec.get("optimal_min") or EC.optimal_low
        ec_opt_hi = t_bounds_ec.get("optimal_max") or EC.optimal_high

        t_bounds_ph = thresholds.get(PARAM_PH, {}) if thresholds else {}
        ph_opt_lo = t_bounds_ph.get("optimal_min") or PH.optimal_low
        ph_opt_hi = t_bounds_ph.get("optimal_max") or PH.optimal_high

        ec_ok = ec_opt_lo <= ec <= ec_opt_hi
        ph_ok = ph_opt_lo <= ph <= ph_opt_hi

        ec_score = 100.0
        if ec < ec_opt_lo:
            ec_score = max(0.0, 100.0 - (ec_opt_lo - ec) / ec_opt_lo * 70.0)
        elif ec > ec_opt_hi:
            ec_score = max(0.0, 100.0 - (ec - ec_opt_hi) / ec_opt_hi * 70.0)

        ph_score = 100.0
        if ph < ph_opt_lo:
            ph_score = max(0.0, 100.0 - (ph_opt_lo - ph) / ph_opt_lo * 30.0)
        elif ph > ph_opt_hi:
            ph_score = max(0.0, 100.0 - (ph - ph_opt_hi) / (14.0 - ph_opt_hi) * 30.0)

        return (ec_score * 0.6 + ph_score * 0.4)

    def _disease_score(self, T: float, sm: float, thresholds: Optional[ThresholdMap] = None) -> float:
        """100 = no disease pressure; lower = higher Phytophthora risk."""
        t_bounds = thresholds.get(PARAM_PHYTOPHTHORA, {}) if thresholds else {}
        opt_lo = t_bounds.get("optimal_min") or PHYTOPHTHORA.temp_favour_low
        opt_hi = t_bounds.get("optimal_max") or PHYTOPHTHORA.temp_favour_high
        crit_hi = t_bounds.get("critical_max") or PHYTOPHTHORA.moisture_critical
        warn_hi = t_bounds.get("warn_max") or PHYTOPHTHORA.moisture_warn

        in_range = opt_lo <= T <= opt_hi
        if not in_range:
            return 100.0
        if sm >= crit_hi:
            return 20.0
        if sm >= warn_hi:
            ratio = (sm - warn_hi) / (
                crit_hi - warn_hi
            )
            return 100.0 - ratio * 80.0
        return 100.0

    def _find_limiting_factors(
        self,
        temp: float,
        water: float,
        nutrient: float,
        disease: float,
    ) -> list[str]:
        scored = [
            ("temperature", temp),
            ("water/moisture", water),
            ("nutrient balance (EC/pH)", nutrient),
            ("disease pressure", disease),
        ]
        scored.sort(key=lambda x: x[1])
        return [name for name, score in scored if score < 70]


def _status(risks: list[dict]) -> str:
    if any(r["severity"] == "critical" for r in risks):
        return "critical"
    if any(r["severity"] == "warning" for r in risks):
        return "warning"
    return "ok"
