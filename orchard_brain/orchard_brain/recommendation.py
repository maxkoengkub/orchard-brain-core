"""RecommendationEngine — derives actionable recommendations from assessments.

Recommendations map directly to the action types recognised by the existing
``ActionSubscriber`` / ``VALID_ACTIONS`` set where an automated actuator exists,
or carry a descriptive advisory key otherwise.

Priority levels
───────────────
  "critical"  — act within minutes; plant or crop damage imminent
  "high"      — act within hours
  "medium"    — act within 24 hours
  "low"       — informational / preventive; schedule at convenience

Confidence scores  (0.0 – 1.0)
────────────────────────────────
Each recommendation includes a ``confidence`` value that scales linearly with
how far the reading has deviated from the relevant threshold:

  At the warning boundary   → confidence ≈ 0.60
  At the critical boundary  → confidence ≈ 0.95
  Beyond critical boundary  → confidence = 0.97

Formula:
  ratio  = |value − warn_boundary| / |critical_boundary − warn_boundary|
  confidence = clamp(0.60 + ratio × 0.37, 0.60, 0.97)

This makes decisions fully explainable: the further the reading is from the
safe zone, the more certain the recommendation.

Output format per recommendation item:
  {
      "action":     str,   # matches VALID_ACTIONS or advisory key
      "priority":   str,   # "critical" | "high" | "medium" | "low"
      "reason":     str,   # human-readable explanation with threshold citations
      "confidence": float, # 0.0-1.0
  }

Design rules
────────────
* One condition → at most one recommendation (first/highest priority wins).
* Recommendations are ordered: critical → high → medium → low.
* All thresholds come from _thresholds.py for consistency.
"""
from __future__ import annotations

from typing import TypedDict

from ._thresholds import (
    EC, HUMIDITY, PH, PHYTOPHTHORA, TEMPERATURE, VPD, compute_vpd_kpa,
)
from .health import HealthResult
from .risk import Risk


class Recommendation(TypedDict):
    action: str
    priority: str
    reason: str
    confidence: float


_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _confidence(
    value: float,
    warn_boundary: float,
    critical_boundary: float,
) -> float:
    """Linear confidence from 0.60 (at warn) to 0.97 (at/beyond critical).

    Handles both higher-is-worse and lower-is-worse directions automatically
    by working with absolute distances.
    """
    span = abs(critical_boundary - warn_boundary)
    if span < 1e-9:
        return 0.80
    deviation = abs(value - warn_boundary)
    ratio = min(1.0, deviation / span)
    return round(0.60 + ratio * 0.37, 2)


class RecommendationEngine:
    """Stateless engine — call ``recommend(temperature, humidity, ec, ph, ...)``.

    Accepts the outputs of ``HealthAssessment`` and ``RiskAssessment`` so the
    caller (``OrchardBrain``) can pass pre-computed values without re-running
    the logic.
    """

    def recommend(
        self,
        temperature: float,
        humidity: float,
        ec: float,
        ph: float,
        health_result: HealthResult | None = None,
        risks: list[Risk] | None = None,
    ) -> list[Recommendation]:
        """Return a deduplicated, priority-sorted list of recommendations."""
        vpd = compute_vpd_kpa(temperature, humidity)

        recs: list[Recommendation] = []
        recs.extend(self._temperature_recommendations(temperature))
        recs.extend(self._water_recommendations(humidity, health_result))
        recs.extend(self._nutrient_ec_recommendations(ec))
        recs.extend(self._nutrient_ph_recommendations(ph))
        recs.extend(self._vpd_recommendations(vpd, temperature, humidity))
        recs.extend(self._phytophthora_recommendations(temperature, humidity))
        recs.extend(self._compound_recommendations(temperature, humidity, ec, ph))

        # Deduplicate by action key (first occurrence = highest priority)
        seen: set[str] = set()
        unique: list[Recommendation] = []
        for rec in recs:
            if rec["action"] not in seen:
                seen.add(rec["action"])
                unique.append(rec)

        unique.sort(key=lambda r: _PRIORITY_ORDER[r["priority"]])
        return unique

    # ---------------------------------------------------------------- temperature

    @staticmethod
    def _temperature_recommendations(temperature: float) -> list[Recommendation]:
        recs: list[Recommendation] = []

        if temperature >= TEMPERATURE.critical_high:
            recs.append(Recommendation(
                action="trigger_micro_sprinkler_cooling",
                priority="critical",
                reason=(
                    f"Temperature {temperature:.1f} °C exceeds critical threshold "
                    f"{TEMPERATURE.critical_high:.1f} °C. Activate micro-sprinkler "
                    "cooling immediately to prevent heat damage and fruit drop "
                    "(Haifa Guide: >38 °C causes leaf scorch)."
                ),
                confidence=_confidence(
                    temperature, TEMPERATURE.warn_high, TEMPERATURE.critical_high
                ),
            ))
        elif temperature >= TEMPERATURE.warn_high:
            recs.append(Recommendation(
                action="trigger_micro_sprinkler_cooling",
                priority="high",
                reason=(
                    f"Temperature {temperature:.1f} °C exceeds warning high "
                    f"{TEMPERATURE.warn_high:.1f} °C. Start micro-sprinkler "
                    "cooling to prevent heat stress accumulation."
                ),
                confidence=_confidence(
                    temperature, TEMPERATURE.warn_high, TEMPERATURE.critical_high
                ),
            ))

        if temperature <= TEMPERATURE.critical_low:
            recs.append(Recommendation(
                action="apply_frost_protection",
                priority="critical",
                reason=(
                    f"Temperature {temperature:.1f} °C is at or below critical low "
                    f"{TEMPERATURE.critical_low:.1f} °C. Apply frost protection "
                    "immediately — chilling injury is imminent."
                ),
                confidence=_confidence(
                    temperature, TEMPERATURE.warn_low, TEMPERATURE.critical_low
                ),
            ))
        elif temperature <= TEMPERATURE.warn_low:
            recs.append(Recommendation(
                action="apply_frost_protection",
                priority="high",
                reason=(
                    f"Temperature {temperature:.1f} °C is at or below warning low "
                    f"{TEMPERATURE.warn_low:.1f} °C. Prepare cold-protection measures "
                    "(research: <22 °C stunts durian growth and delays fruiting)."
                ),
                confidence=_confidence(
                    temperature, TEMPERATURE.warn_low, TEMPERATURE.critical_low
                ),
            ))

        return recs

    # ---------------------------------------------------------------- water

    @staticmethod
    def _water_recommendations(
        humidity: float,
        health_result: HealthResult | None,
    ) -> list[Recommendation]:
        recs: list[Recommendation] = []
        water_stress = health_result.water_stress if health_result else None

        # Drought conditions
        if humidity <= HUMIDITY.critical_low:
            recs.append(Recommendation(
                action="trigger_irrigation",
                priority="critical",
                reason=(
                    f"Soil moisture {humidity:.1f} % is at critical low "
                    f"{HUMIDITY.critical_low:.1f} %. Trigger irrigation immediately "
                    "— wilting and irreversible root damage imminent "
                    "(research: <20-30 % VWC = severe drought)."
                ),
                confidence=_confidence(
                    humidity, HUMIDITY.warn_low, HUMIDITY.critical_low
                ),
            ))
        elif humidity <= HUMIDITY.warn_low:
            recs.append(Recommendation(
                action="trigger_irrigation",
                priority="high",
                reason=(
                    f"Soil moisture {humidity:.1f} % is below warning low "
                    f"{HUMIDITY.warn_low:.1f} %. Trigger irrigation promptly to "
                    "relieve drought stress (FAO optimal: 40-60 % VWC)."
                ),
                confidence=_confidence(
                    humidity, HUMIDITY.warn_low, HUMIDITY.critical_low
                ),
            ))
        elif humidity < HUMIDITY.optimal_low:
            recs.append(Recommendation(
                action="trigger_irrigation",
                priority="medium",
                reason=(
                    f"Soil moisture {humidity:.1f} % is below optimal minimum "
                    f"{HUMIDITY.optimal_low:.1f} % VWC. Schedule a light "
                    "irrigation cycle (FAO optimal: 40-60 % VWC)."
                ),
                confidence=0.62,
            ))

        # Waterlogging conditions
        if humidity >= HUMIDITY.critical_high:
            recs.append(Recommendation(
                action="stop_irrigation",
                priority="critical",
                reason=(
                    f"Soil moisture {humidity:.1f} % is at critical high "
                    f"{HUMIDITY.critical_high:.1f} %. Stop all irrigation "
                    "immediately — root anaerobia and fungal disease risk is severe."
                ),
                confidence=_confidence(
                    humidity, HUMIDITY.warn_high, HUMIDITY.critical_high
                ),
            ))
        elif humidity >= HUMIDITY.warn_high:
            recs.append(Recommendation(
                action="stop_irrigation",
                priority="high",
                reason=(
                    f"Soil moisture {humidity:.1f} % exceeds warning high "
                    f"{HUMIDITY.warn_high:.1f} %. Stop irrigation and allow "
                    "drainage before the next watering cycle."
                ),
                confidence=_confidence(
                    humidity, HUMIDITY.warn_high, HUMIDITY.critical_high
                ),
            ))
        elif humidity > HUMIDITY.optimal_high:
            recs.append(Recommendation(
                action="stop_irrigation",
                priority="medium",
                reason=(
                    f"Soil moisture {humidity:.1f} % exceeds optimal maximum "
                    f"{HUMIDITY.optimal_high:.1f} % VWC. Reduce next irrigation "
                    "volume or delay the schedule."
                ),
                confidence=0.62,
            ))

        # High water_stress compound advisory
        if water_stress is not None and water_stress >= 75 and humidity < HUMIDITY.optimal_low:
            recs.append(Recommendation(
                action="inspect_irrigation_system",
                priority="high",
                reason=(
                    f"Water stress index {water_stress} is critically high. "
                    "Inspect irrigation lines for blockages or failures before "
                    "the next scheduled run."
                ),
                confidence=round(min(0.97, 0.60 + (water_stress - 75) / 25 * 0.37), 2),
            ))

        return recs

    # ---------------------------------------------------------------- EC

    @staticmethod
    def _nutrient_ec_recommendations(ec: float) -> list[Recommendation]:
        recs: list[Recommendation] = []

        if ec <= EC.critical_low:
            recs.append(Recommendation(
                action="adjust_fertigation_ratio_to_high_pk",
                priority="critical",
                reason=(
                    f"EC {ec:.0f} µS/cm is at critical low {EC.critical_low:.0f} µS/cm. "
                    "Apply high-PK fertigation immediately to prevent severe nutrient "
                    "starvation (Tang et al., 2024: balanced NPK critical for yield)."
                ),
                confidence=_confidence(ec, EC.warn_low, EC.critical_low),
            ))
        elif ec <= EC.warn_low:
            recs.append(Recommendation(
                action="adjust_fertigation_ratio_to_high_pk",
                priority="high",
                reason=(
                    f"EC {ec:.0f} µS/cm is below warning low {EC.warn_low:.0f} µS/cm. "
                    "Increase fertigation concentration in the next irrigation cycle."
                ),
                confidence=_confidence(ec, EC.warn_low, EC.critical_low),
            ))
        elif ec < EC.optimal_low:
            recs.append(Recommendation(
                action="adjust_fertigation_ratio_to_high_pk",
                priority="medium",
                reason=(
                    f"EC {ec:.0f} µS/cm is below optimal minimum "
                    f"{EC.optimal_low:.0f} µS/cm. Consider a light fertigation "
                    "boost to restore optimal nutrient levels."
                ),
                confidence=0.62,
            ))

        if ec >= EC.critical_high:
            recs.append(Recommendation(
                action="flush_irrigation_to_reduce_ec",
                priority="critical",
                reason=(
                    f"EC {ec:.0f} µS/cm is at critical high {EC.critical_high:.0f} µS/cm. "
                    "Flush the root zone with clean water immediately to prevent "
                    "salt toxicity."
                ),
                confidence=_confidence(ec, EC.warn_high, EC.critical_high),
            ))
        elif ec >= EC.warn_high:
            recs.append(Recommendation(
                action="flush_irrigation_to_reduce_ec",
                priority="high",
                reason=(
                    f"EC {ec:.0f} µS/cm exceeds warning high {EC.warn_high:.0f} µS/cm. "
                    "Plan a leaching irrigation cycle to reduce salt accumulation."
                ),
                confidence=_confidence(ec, EC.warn_high, EC.critical_high),
            ))
        elif ec > EC.optimal_high:
            recs.append(Recommendation(
                action="flush_irrigation_to_reduce_ec",
                priority="low",
                reason=(
                    f"EC {ec:.0f} µS/cm slightly exceeds optimal maximum "
                    f"{EC.optimal_high:.0f} µS/cm. Monitor and reduce "
                    "fertigation concentration at next opportunity."
                ),
                confidence=0.62,
            ))

        return recs

    # ---------------------------------------------------------------- pH

    @staticmethod
    def _nutrient_ph_recommendations(ph: float) -> list[Recommendation]:
        """pH recommendations — research basis: optimal 5.5-6.5 (Ngoc et al., 2024)."""
        recs: list[Recommendation] = []

        if ph <= PH.critical_low:
            recs.append(Recommendation(
                action="apply_lime_to_raise_ph",
                priority="critical",
                reason=(
                    f"pH {ph:.2f} is at critical low {PH.critical_low:.1f}. "
                    "Apply agricultural lime immediately — full Ca/Mg/P lock-out "
                    "is imminent at this acidity level."
                ),
                confidence=_confidence(ph, PH.warn_low, PH.critical_low),
            ))
        elif ph <= PH.warn_low:
            recs.append(Recommendation(
                action="apply_lime_to_raise_ph",
                priority="high",
                reason=(
                    f"pH {ph:.2f} is below warning low {PH.warn_low:.1f}. "
                    "Apply lime or dolomite to raise pH and restore P availability "
                    "(durian optimal pH: 5.5-6.5)."
                ),
                confidence=_confidence(ph, PH.warn_low, PH.critical_low),
            ))
        elif ph < PH.optimal_low:
            recs.append(Recommendation(
                action="apply_lime_to_raise_ph",
                priority="medium",
                reason=(
                    f"pH {ph:.2f} is below optimal minimum {PH.optimal_low:.1f}. "
                    "Schedule a lime application to return pH to optimal range "
                    "(research: durian optimal pH 5.5-6.5)."
                ),
                confidence=0.62,
            ))

        if ph >= PH.critical_high:
            recs.append(Recommendation(
                action="apply_sulfur_to_lower_ph",
                priority="critical",
                reason=(
                    f"pH {ph:.2f} is at critical high {PH.critical_high:.1f}. "
                    "Apply elemental sulfur or acidifying fertiliser urgently — "
                    "Fe/Zn/Mn lock-out is active (research: optimal pH ≤6.5)."
                ),
                confidence=_confidence(ph, PH.warn_high, PH.critical_high),
            ))
        elif ph >= PH.warn_high:
            recs.append(Recommendation(
                action="apply_sulfur_to_lower_ph",
                priority="high",
                reason=(
                    f"pH {ph:.2f} exceeds warning high {PH.warn_high:.1f}. "
                    "Apply sulfur-based acidifier to lower pH and restore "
                    "micronutrient availability (research: optimal pH ≤6.5)."
                ),
                confidence=_confidence(ph, PH.warn_high, PH.critical_high),
            ))
        elif ph > PH.optimal_high:
            recs.append(Recommendation(
                action="apply_sulfur_to_lower_ph",
                priority="medium",
                reason=(
                    f"pH {ph:.2f} exceeds optimal maximum {PH.optimal_high:.1f}. "
                    "Monitor pH trend; plan acidification if it continues to rise "
                    "(durian optimal pH 5.5-6.5; Ngoc et al., 2024)."
                ),
                confidence=0.62,
            ))

        return recs

    # ---------------------------------------------------------------- VPD

    @staticmethod
    def _vpd_recommendations(
        vpd: float,
        temperature: float,
        humidity: float,
    ) -> list[Recommendation]:
        """Vapor Pressure Deficit recommendations.

        High VPD increases transpiration and accelerates soil moisture depletion.
        Recommendations target reducing evaporative load through cooling or misting.
        """
        recs: list[Recommendation] = []

        if vpd >= VPD.critical_high:
            recs.append(Recommendation(
                action="trigger_micro_sprinkler_cooling",
                priority="critical",
                reason=(
                    f"VPD {vpd:.2f} kPa (T={temperature:.1f} °C, H={humidity:.1f} %) "
                    f"exceeds critical {VPD.critical_high:.1f} kPa — stomatal closure "
                    "and severe water stress are occurring even if soil moisture is "
                    "adequate. Activate misting/sprinkler to lower atmospheric demand."
                ),
                confidence=_confidence(vpd, VPD.warn_high, VPD.critical_high),
            ))
        elif vpd >= VPD.warn_high:
            recs.append(Recommendation(
                action="trigger_micro_sprinkler_cooling",
                priority="high",
                reason=(
                    f"VPD {vpd:.2f} kPa (T={temperature:.1f} °C, H={humidity:.1f} %) "
                    f"exceeds warning {VPD.warn_high:.1f} kPa — evaporative demand "
                    "is high; activate misting to reduce canopy stress."
                ),
                confidence=_confidence(vpd, VPD.warn_high, VPD.critical_high),
            ))

        return recs

    # ---------------------------------------------------------------- Phytophthora

    @staticmethod
    def _phytophthora_recommendations(
        temperature: float,
        humidity: float,
    ) -> list[Recommendation]:
        """Recommendations for Phytophthora disease risk.

        Triggered when warm temperature × high soil moisture create conditions
        that favour P. palmivora (Guest & Drenth, 2004).
        """
        recs: list[Recommendation] = []

        temp_in_range = PHYTOPHTHORA.temp_favour_low <= temperature <= PHYTOPHTHORA.temp_favour_high

        if temp_in_range and humidity >= PHYTOPHTHORA.moisture_critical:
            conf = _confidence(
                humidity,
                PHYTOPHTHORA.moisture_warn,
                PHYTOPHTHORA.moisture_critical,
            )
            recs.append(Recommendation(
                action="inspect_for_phytophthora",
                priority="critical",
                reason=(
                    f"Critical Phytophthora conditions: T={temperature:.1f} °C and "
                    f"soil moisture {humidity:.1f} % ≥ {PHYTOPHTHORA.moisture_critical:.0f} %. "
                    "Inspect all trees for root/stem canker. Apply preventive "
                    "phosphonate fungicide (Guest & Drenth, 2004)."
                ),
                confidence=conf,
            ))
            recs.append(Recommendation(
                action="apply_mulch_for_disease_prevention",
                priority="high",
                reason=(
                    "Apply organic mulch (10-15 cm) around tree bases to reduce "
                    "soil splash, improve drainage, and suppress Phytophthora "
                    "spread under current wet and warm conditions."
                ),
                confidence=round(conf * 0.9, 2),
            ))
        elif temp_in_range and humidity >= PHYTOPHTHORA.moisture_warn:
            conf = _confidence(
                humidity,
                PHYTOPHTHORA.moisture_warn,
                PHYTOPHTHORA.moisture_critical,
            )
            recs.append(Recommendation(
                action="apply_mulch_for_disease_prevention",
                priority="medium",
                reason=(
                    f"Phytophthora-favourable conditions: T={temperature:.1f} °C and "
                    f"soil moisture {humidity:.1f} % — apply mulch and improve "
                    "drainage to reduce infection risk (Guest & Drenth, 2004)."
                ),
                confidence=conf,
            ))

        return recs

    # ---------------------------------------------------------------- compound

    @staticmethod
    def _compound_recommendations(
        temperature: float,
        humidity: float,
        ec: float,
        ph: float,
    ) -> list[Recommendation]:
        """Multi-variable conditions that require a combined response."""
        recs: list[Recommendation] = []

        # Combined heat + drought: nutrient uptake collapses
        is_hot = temperature >= TEMPERATURE.warn_high
        is_dry = humidity < HUMIDITY.optimal_low
        if is_hot and is_dry:
            recs.append(Recommendation(
                action="reduce_fertigation_until_heat_stress_resolved",
                priority="high",
                reason=(
                    f"Combined heat ({temperature:.1f} °C) and drought "
                    f"({humidity:.1f} % < {HUMIDITY.optimal_low:.0f} % VWC). "
                    "Nutrient uptake is severely impaired at high temperature with "
                    "low soil moisture — reduce fertigation concentration to avoid "
                    "EC build-up during stress (research: nutrient uptake needs "
                    "adequate water flow through roots)."
                ),
                confidence=0.75,
            ))

        # Flowering trigger advisory — Eguchi et al. (2024): ~50 days after 15-day dry spell
        is_dry_for_flowering = humidity < HUMIDITY.warn_low
        is_cool_enough = temperature <= TEMPERATURE.optimal_high
        if is_dry_for_flowering and is_cool_enough:
            recs.append(Recommendation(
                action="anticipate_flowering_trigger",
                priority="low",
                reason=(
                    f"Dry-spell conditions detected: soil moisture {humidity:.1f} % "
                    f"< {HUMIDITY.warn_low:.0f} % with T={temperature:.1f} °C. "
                    "If this persists for ~15 days, flowering initiation may begin "
                    "~50 days later (Eguchi et al., 2024). Schedule bud monitoring "
                    "and prepare pre-flowering nutrient program "
                    "(reduce N, maintain high K)."
                ),
                confidence=0.65,
            ))

        # Optimal conditions — positive reinforcement advisory
        temp_ok = TEMPERATURE.optimal_low <= temperature <= TEMPERATURE.optimal_high
        hum_ok = HUMIDITY.optimal_low <= humidity <= HUMIDITY.optimal_high
        ec_ok = EC.optimal_low <= ec <= EC.optimal_high
        ph_ok = PH.optimal_low <= ph <= PH.optimal_high
        if temp_ok and hum_ok and ec_ok and ph_ok:
            recs.append(Recommendation(
                action="maintain_current_conditions",
                priority="low",
                reason=(
                    "All parameters are within optimal ranges "
                    f"(T={temperature:.1f} °C, soil moisture={humidity:.1f} %, "
                    f"EC={ec:.0f} µS/cm, pH={ph:.2f}). "
                    "Continue current irrigation and fertigation schedule. "
                    "Next soil test recommended in 4 weeks."
                ),
                confidence=0.90,
            ))

        return recs
