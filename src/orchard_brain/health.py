"""HealthAssessment — computes health_score, water_stress, nutrient_stress, and VPD.

All decisions are rule-based and fully explainable: every output value is
derived from a documented linear mapping against agronomic thresholds defined
in _thresholds.py.  No statistical models or ML weights are used.

Scoring model
─────────────
Three independent sub-scores are computed on a 0–100 scale:

  temperature_score  (weight 0.35) — proximity to optimal 25–32 °C
  water_score        (weight 0.40) — inverse of water_stress
  nutrient_score     (weight 0.25) — inverse of nutrient_stress

  health_score = temperature_score × 0.35
               + water_score       × 0.40
               + nutrient_score    × 0.25

Water stress (research basis: 40-60 % VWC optimal)
────────────
  humidity < optimal_low (40%)  → drought  = (optimal_low − h) / optimal_low  × 100
  humidity > optimal_high (60%) → overwater = (h − optimal_high) / (100 − optimal_high) × 100
  otherwise                     → 0

Nutrient stress
───────────────
EC component  (0–70 contribution):
  ec < optimal_low  → (optimal_low − ec) / optimal_low × 70
  ec > optimal_high → (ec − optimal_high) / optimal_high × 70

pH component  (0–30 contribution, research basis: pH 5.5-6.5 optimal):
  ph < optimal_low  → (optimal_low − ph) / optimal_low × 30
  ph > optimal_high → (ph − optimal_high) / (14 − optimal_high) × 30

nutrient_stress = clamp(ec_component + ph_component, 0, 100)

VPD (diagnostic)
────────────────
Vapor Pressure Deficit is computed from temperature and humidity and exposed
as a diagnostic field (vpd_kpa) for logging and downstream assessors.
It is not included in health_score directly, but drives VPD risks in
RiskAssessment and priority-boosting in RecommendationEngine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ._thresholds import EC, HUMIDITY, PH, TEMPERATURE, compute_vpd_kpa
from .knowledge.threshold_engine import (
    ThresholdMap,
    PARAM_TEMPERATURE,
    PARAM_HUMIDITY,
    PARAM_EC,
    PARAM_PH
)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class HealthResult:
    health_score: int
    water_stress: int
    nutrient_stress: int
    temperature_score: int   # 0-100; exposed for diagnostics / unit tests
    vpd_kpa: float           # Vapor Pressure Deficit (kPa); diagnostic only
    _water_stress_raw: float
    _nutrient_stress_raw: float
    _temperature_score_raw: float


class HealthAssessment:
    """Stateless assessor — call ``assess(temperature, humidity, ec, ph)``.

    All parameters follow the same conventions used in ``SensorReading``
    (validator.py):  temperature in °C, humidity in %, ec in µS/cm, ph 0–14.

    Returns a ``HealthResult`` with integer scores for the public API and
    float raw values for unit-testing precision.
    """

    # Penalty scaling constants (documented here for full explainability)
    _TEMP_PENALTY_PER_DEG_BELOW: float = 8.0   # pts lost per °C below opt_low
    _TEMP_PENALTY_PER_DEG_ABOVE: float = 12.0  # pts lost per °C above opt_high
    _EC_MAX_CONTRIBUTION: float = 70.0
    _PH_MAX_CONTRIBUTION: float = 30.0
    _W_TEMPERATURE: float = 0.35
    _W_WATER: float = 0.40
    _W_NUTRIENT: float = 0.25

    # ---------------------------------------------------------------------- API

    def assess(
        self,
        temperature: float,
        humidity: float,
        ec: float,
        ph: float,
        thresholds: Optional[ThresholdMap] = None,
    ) -> HealthResult:
        """Return health metrics for the given sensor reading."""
        water_stress_raw = self._compute_water_stress(humidity, thresholds)
        nutrient_stress_raw = self._compute_nutrient_stress(ec, ph, thresholds)
        temperature_score_raw = self._compute_temperature_score(temperature, thresholds)
        vpd = compute_vpd_kpa(temperature, humidity)

        water_score = 100.0 - water_stress_raw
        nutrient_score = 100.0 - nutrient_stress_raw

        health_raw = (
            temperature_score_raw * self._W_TEMPERATURE
            + water_score         * self._W_WATER
            + nutrient_score      * self._W_NUTRIENT
        )

        return HealthResult(
            health_score=round(_clamp(health_raw)),
            water_stress=round(water_stress_raw),
            nutrient_stress=round(nutrient_stress_raw),
            temperature_score=round(temperature_score_raw),
            vpd_kpa=round(vpd, 3),
            _water_stress_raw=water_stress_raw,
            _nutrient_stress_raw=nutrient_stress_raw,
            _temperature_score_raw=temperature_score_raw,
        )

    # ----------------------------------------------------------------- internal

    def _compute_water_stress(self, humidity: float, thresholds: Optional[ThresholdMap]) -> float:
        """Return water stress 0–100 (higher = worse)."""
        t_bounds = thresholds.get(PARAM_HUMIDITY, {}) if thresholds else {}
        opt_lo = t_bounds.get("optimal_min") or HUMIDITY.optimal_low
        opt_hi = t_bounds.get("optimal_max") or HUMIDITY.optimal_high

        if humidity < opt_lo:
            # Drought: linear from 0 stress at opt_lo to 100 stress at 0 %
            return _clamp((opt_lo - humidity) / opt_lo * 100.0)

        if humidity > opt_hi:
            # Overwatering: linear from 0 stress at opt_hi to 100 stress at 100 %
            return _clamp((humidity - opt_hi) / (100.0 - opt_hi) * 100.0)

        return 0.0

    def _compute_nutrient_stress(self, ec: float, ph: float, thresholds: Optional[ThresholdMap]) -> float:
        """Return nutrient stress 0–100 (higher = worse).

        EC contributes up to 70 points; pH contributes up to 30 points.
        The sum is clamped to [0, 100].
        """
        ec_contribution = self._ec_component(ec, thresholds)
        ph_contribution = self._ph_component(ph, thresholds)
        return _clamp(ec_contribution + ph_contribution)

    def _ec_component(self, ec: float, thresholds: Optional[ThresholdMap]) -> float:
        t_bounds = thresholds.get(PARAM_EC, {}) if thresholds else {}
        opt_lo = t_bounds.get("optimal_min") or EC.optimal_low
        opt_hi = t_bounds.get("optimal_max") or EC.optimal_high
        max_c = self._EC_MAX_CONTRIBUTION

        if ec < opt_lo:
            return _clamp((opt_lo - ec) / opt_lo * max_c, 0.0, max_c)

        if ec > opt_hi:
            return _clamp((ec - opt_hi) / opt_hi * max_c, 0.0, max_c)

        return 0.0

    def _ph_component(self, ph: float, thresholds: Optional[ThresholdMap]) -> float:
        t_bounds = thresholds.get(PARAM_PH, {}) if thresholds else {}
        opt_lo = t_bounds.get("optimal_min") or PH.optimal_low
        opt_hi = t_bounds.get("optimal_max") or PH.optimal_high
        max_c = self._PH_MAX_CONTRIBUTION

        if ph < opt_lo:
            return _clamp((opt_lo - ph) / opt_lo * max_c, 0.0, max_c)

        if ph > opt_hi:
            return _clamp((ph - opt_hi) / (14.0 - opt_hi) * max_c, 0.0, max_c)

        return 0.0

    def _compute_temperature_score(self, temperature: float, thresholds: Optional[ThresholdMap]) -> float:
        """Return temperature sub-score 0–100 (100 = perfectly optimal)."""
        t_bounds = thresholds.get(PARAM_TEMPERATURE, {}) if thresholds else {}
        opt_lo = t_bounds.get("optimal_min") or TEMPERATURE.optimal_low
        opt_hi = t_bounds.get("optimal_max") or TEMPERATURE.optimal_high

        if opt_lo <= temperature <= opt_hi:
            return 100.0

        if temperature < opt_lo:
            penalty = (opt_lo - temperature) * self._TEMP_PENALTY_PER_DEG_BELOW
            return _clamp(100.0 - penalty)

        # temperature > opt_hi
        penalty = (temperature - opt_hi) * self._TEMP_PENALTY_PER_DEG_ABOVE
        return _clamp(100.0 - penalty)
