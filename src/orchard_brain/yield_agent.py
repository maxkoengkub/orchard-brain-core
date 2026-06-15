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

from ._agent_base import AgentAssessment
from ._thresholds import EC, HUMIDITY, PH, PHYTOPHTHORA, TEMPERATURE, VPD, compute_vpd_kpa
from .orchard_memory import SensorSnapshot, TrendResult


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
    ) -> AgentAssessment:
        trends = trends or []
        T = snapshot.temperature
        sm = snapshot.soil_moisture
        ph = snapshot.ph
        ec = snapshot.ec
        vpd = snapshot.vpd or compute_vpd_kpa(T, snapshot.humidity)

        # ── component scores (0–100)
        temp_score = self._temperature_score(T)
        water_score = self._water_score(sm, vpd)
        nutrient_score = self._nutrient_score(ec, ph)
        disease_score = self._disease_score(T, sm)

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

    def _temperature_score(self, T: float) -> float:
        opt_lo, opt_hi = TEMPERATURE.optimal_low, TEMPERATURE.optimal_high
        if opt_lo <= T <= opt_hi:
            return 100.0
        if T < opt_lo:
            return max(0.0, 100.0 - (opt_lo - T) * 8.0)
        return max(0.0, 100.0 - (T - opt_hi) * 12.0)

    def _water_score(self, sm: float, vpd: float) -> float:
        opt_lo, opt_hi = HUMIDITY.optimal_low, HUMIDITY.optimal_high
        if opt_lo <= sm <= opt_hi:
            base = 100.0
        elif sm < opt_lo:
            base = max(0.0, 100.0 - (opt_lo - sm) / opt_lo * 100.0)
        else:
            base = max(0.0, 100.0 - (sm - opt_hi) / (100.0 - opt_hi) * 100.0)
        # VPD penalty (compare kPa against VPD thresholds, not temperature thresholds)
        if vpd >= VPD.critical_high:
            base *= 0.5
        elif vpd >= VPD.warn_high:
            base *= 0.75
        return base

    def _nutrient_score(self, ec: float, ph: float) -> float:
        ec_ok = EC.optimal_low <= ec <= EC.optimal_high
        ph_ok = PH.optimal_low <= ph <= PH.optimal_high

        ec_score = 100.0
        if ec < EC.optimal_low:
            ec_score = max(0.0, 100.0 - (EC.optimal_low - ec) / EC.optimal_low * 70.0)
        elif ec > EC.optimal_high:
            ec_score = max(0.0, 100.0 - (ec - EC.optimal_high) / EC.optimal_high * 70.0)

        ph_score = 100.0
        if ph < PH.optimal_low:
            ph_score = max(0.0, 100.0 - (PH.optimal_low - ph) / PH.optimal_low * 30.0)
        elif ph > PH.optimal_high:
            ph_score = max(0.0, 100.0 - (ph - PH.optimal_high) / (14.0 - PH.optimal_high) * 30.0)

        return (ec_score * 0.6 + ph_score * 0.4)

    def _disease_score(self, T: float, sm: float) -> float:
        """100 = no disease pressure; lower = higher Phytophthora risk."""
        in_range = PHYTOPHTHORA.temp_favour_low <= T <= PHYTOPHTHORA.temp_favour_high
        if not in_range:
            return 100.0
        if sm >= PHYTOPHTHORA.moisture_critical:
            return 20.0
        if sm >= PHYTOPHTHORA.moisture_warn:
            ratio = (sm - PHYTOPHTHORA.moisture_warn) / (
                PHYTOPHTHORA.moisture_critical - PHYTOPHTHORA.moisture_warn
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
