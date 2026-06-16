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

from typing import TypedDict, Optional

from ._thresholds import (
    EC, HUMIDITY, PH, PHYTOPHTHORA, TEMPERATURE, VPD, compute_vpd_kpa,
)
from .health import HealthResult
from .risk import Risk
from .knowledge.threshold_engine import (
    ThresholdMap,
    PARAM_TEMPERATURE,
    PARAM_HUMIDITY,
    PARAM_EC,
    PARAM_PH,
    PARAM_VPD,
    PARAM_PHYTOPHTHORA
)


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
        thresholds: Optional[ThresholdMap] = None,
    ) -> list[Recommendation]:
        """Return a deduplicated, priority-sorted list of recommendations."""
        vpd = compute_vpd_kpa(temperature, humidity)

        recs: list[Recommendation] = []
        recs.extend(self._temperature_recommendations(temperature, thresholds))
        recs.extend(self._water_recommendations(humidity, health_result, thresholds))
        recs.extend(self._nutrient_ec_recommendations(ec, thresholds))
        recs.extend(self._nutrient_ph_recommendations(ph, thresholds))
        recs.extend(self._vpd_recommendations(vpd, temperature, humidity, thresholds))
        recs.extend(self._phytophthora_recommendations(temperature, humidity, thresholds))
        recs.extend(self._compound_recommendations(temperature, humidity, ec, ph, thresholds))

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
    def _temperature_recommendations(temperature: float, thresholds: Optional[ThresholdMap] = None) -> list[Recommendation]:
        recs: list[Recommendation] = []
        t_bounds = thresholds.get(PARAM_TEMPERATURE, {}) if thresholds else {}
        crit_hi = t_bounds.get("critical_max") or TEMPERATURE.critical_high
        warn_hi = t_bounds.get("warn_max") or TEMPERATURE.warn_high
        crit_lo = t_bounds.get("critical_min") or TEMPERATURE.critical_low
        warn_lo = t_bounds.get("warn_min") or TEMPERATURE.warn_low

        if temperature >= crit_hi:
            recs.append(Recommendation(
                action="trigger_micro_sprinkler_cooling",
                priority="critical",
                reason=(
                    f"Temperature {temperature:.1f} °C exceeds critical threshold "
                    f"{crit_hi:.1f} °C. Activate micro-sprinkler "
                    "cooling immediately to prevent heat damage and fruit drop "
                    "(Haifa Guide: >38 °C causes leaf scorch)."
                ),
                confidence=_confidence(
                    temperature, warn_hi, crit_hi
                ),
            ))
        elif temperature >= warn_hi:
            recs.append(Recommendation(
                action="trigger_micro_sprinkler_cooling",
                priority="high",
                reason=(
                    f"Temperature {temperature:.1f} °C exceeds warning high "
                    f"{warn_hi:.1f} °C. Start micro-sprinkler "
                    "cooling to prevent heat stress accumulation."
                ),
                confidence=_confidence(
                    temperature, warn_hi, crit_hi
                ),
            ))

        if temperature <= crit_lo:
            recs.append(Recommendation(
                action="apply_frost_protection",
                priority="critical",
                reason=(
                    f"Temperature {temperature:.1f} °C is at or below critical low "
                    f"{crit_lo:.1f} °C. Apply frost protection "
                    "immediately — chilling injury is imminent."
                ),
                confidence=_confidence(
                    temperature, warn_lo, crit_lo
                ),
            ))
        elif temperature <= warn_lo:
            recs.append(Recommendation(
                action="apply_frost_protection",
                priority="high",
                reason=(
                    f"Temperature {temperature:.1f} °C is at or below warning low "
                    f"{warn_lo:.1f} °C. Prepare cold-protection measures "
                    "(research: <22 °C stunts durian growth and delays fruiting)."
                ),
                confidence=_confidence(
                    temperature, warn_lo, crit_lo
                ),
            ))

        return recs

    # ---------------------------------------------------------------- water

    @staticmethod
    def _water_recommendations(
        humidity: float,
        health_result: HealthResult | None,
        thresholds: Optional[ThresholdMap] = None,
    ) -> list[Recommendation]:
        recs: list[Recommendation] = []
        water_stress = health_result.water_stress if health_result else None
        
        t_bounds = thresholds.get(PARAM_HUMIDITY, {}) if thresholds else {}
        crit_hi = t_bounds.get("critical_max") or HUMIDITY.critical_high
        warn_hi = t_bounds.get("warn_max") or HUMIDITY.warn_high
        opt_hi = t_bounds.get("optimal_max") or HUMIDITY.optimal_high
        opt_lo = t_bounds.get("optimal_min") or HUMIDITY.optimal_low
        warn_lo = t_bounds.get("warn_min") or HUMIDITY.warn_low
        crit_lo = t_bounds.get("critical_min") or HUMIDITY.critical_low

        # Drought conditions
        if humidity <= crit_lo:
            recs.append(Recommendation(
                action="trigger_irrigation",
                priority="critical",
                reason=(
                    f"Soil moisture {humidity:.1f} % is at critical low "
                    f"{crit_lo:.1f} %. Trigger irrigation immediately "
                    "— wilting and irreversible root damage imminent "
                    "(research: <20-30 % VWC = severe drought)."
                ),
                confidence=_confidence(
                    humidity, warn_lo, crit_lo
                ),
            ))
        elif humidity <= warn_lo:
            recs.append(Recommendation(
                action="trigger_irrigation",
                priority="high",
                reason=(
                    f"Soil moisture {humidity:.1f} % is below warning low "
                    f"{warn_lo:.1f} %. Trigger irrigation promptly to "
                    "relieve drought stress (FAO optimal: 40-60 % VWC)."
                ),
                confidence=_confidence(
                    humidity, warn_lo, crit_lo
                ),
            ))
        elif humidity < opt_lo:
            recs.append(Recommendation(
                action="trigger_irrigation",
                priority="medium",
                reason=(
                    f"Soil moisture {humidity:.1f} % is below optimal minimum "
                    f"{opt_lo:.1f} % VWC. Schedule a light "
                    "irrigation cycle (FAO optimal: 40-60 % VWC)."
                ),
                confidence=0.62,
            ))

        # Waterlogging conditions
        if humidity >= crit_hi:
            recs.append(Recommendation(
                action="stop_irrigation",
                priority="critical",
                reason=(
                    f"Soil moisture {humidity:.1f} % is at critical high "
                    f"{crit_hi:.1f} %. Stop all irrigation "
                    "immediately — root anaerobia and fungal disease risk is severe."
                ),
                confidence=_confidence(
                    humidity, warn_hi, crit_hi
                ),
            ))
        elif humidity >= warn_hi:
            recs.append(Recommendation(
                action="stop_irrigation",
                priority="high",
                reason=(
                    f"Soil moisture {humidity:.1f} % exceeds warning high "
                    f"{warn_hi:.1f} %. Stop irrigation and allow "
                    "drainage before the next watering cycle."
                ),
                confidence=_confidence(
                    humidity, warn_hi, crit_hi
                ),
            ))
        elif humidity > opt_hi:
            recs.append(Recommendation(
                action="stop_irrigation",
                priority="medium",
                reason=(
                    f"Soil moisture {humidity:.1f} % exceeds optimal maximum "
                    f"{opt_hi:.1f} % VWC. Reduce next irrigation "
                    "volume or delay the schedule."
                ),
                confidence=0.62,
            ))

        # High water_stress compound advisory
        if water_stress is not None and water_stress >= 75 and humidity < opt_lo:
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
    def _nutrient_ec_recommendations(ec: float, thresholds: Optional[ThresholdMap] = None) -> list[Recommendation]:
        recs: list[Recommendation] = []
        t_bounds = thresholds.get(PARAM_EC, {}) if thresholds else {}
        crit_hi = t_bounds.get("critical_max") or EC.critical_high
        warn_hi = t_bounds.get("warn_max") or EC.warn_high
        opt_hi = t_bounds.get("optimal_max") or EC.optimal_high
        opt_lo = t_bounds.get("optimal_min") or EC.optimal_low
        warn_lo = t_bounds.get("warn_min") or EC.warn_low
        crit_lo = t_bounds.get("critical_min") or EC.critical_low

        if ec <= crit_lo:
            recs.append(Recommendation(
                action="adjust_fertigation_ratio_to_high_pk",
                priority="critical",
                reason=(
                    f"EC {ec:.0f} µS/cm is at critical low {crit_lo:.0f} µS/cm. "
                    "Apply high-PK fertigation immediately to prevent severe nutrient "
                    "starvation (Tang et al., 2024: balanced NPK critical for yield)."
                ),
                confidence=_confidence(ec, warn_lo, crit_lo),
            ))
        elif ec <= warn_lo:
            recs.append(Recommendation(
                action="adjust_fertigation_ratio_to_high_pk",
                priority="high",
                reason=(
                    f"EC {ec:.0f} µS/cm is below warning low {warn_lo:.0f} µS/cm. "
                    "Increase fertigation concentration in the next irrigation cycle."
                ),
                confidence=_confidence(ec, warn_lo, crit_lo),
            ))
        elif ec < opt_lo:
            recs.append(Recommendation(
                action="adjust_fertigation_ratio_to_high_pk",
                priority="medium",
                reason=(
                    f"EC {ec:.0f} µS/cm is below optimal minimum "
                    f"{opt_lo:.0f} µS/cm. Consider a light fertigation "
                    "boost to restore optimal nutrient levels."
                ),
                confidence=0.62,
            ))

        if ec >= crit_hi:
            recs.append(Recommendation(
                action="flush_irrigation_to_reduce_ec",
                priority="critical",
                reason=(
                    f"EC {ec:.0f} µS/cm is at critical high {crit_hi:.0f} µS/cm. "
                    "Flush the root zone with clean water immediately to prevent "
                    "salt toxicity."
                ),
                confidence=_confidence(ec, warn_hi, crit_hi),
            ))
        elif ec >= warn_hi:
            recs.append(Recommendation(
                action="flush_irrigation_to_reduce_ec",
                priority="high",
                reason=(
                    f"EC {ec:.0f} µS/cm exceeds warning high {warn_hi:.0f} µS/cm. "
                    "Plan a leaching irrigation cycle to reduce salt accumulation."
                ),
                confidence=_confidence(ec, warn_hi, crit_hi),
            ))
        elif ec > opt_hi:
            recs.append(Recommendation(
                action="flush_irrigation_to_reduce_ec",
                priority="low",
                reason=(
                    f"EC {ec:.0f} µS/cm slightly exceeds optimal maximum "
                    f"{opt_hi:.0f} µS/cm. Monitor and reduce "
                    "fertigation concentration at next opportunity."
                ),
                confidence=0.62,
            ))

        return recs

    # ---------------------------------------------------------------- pH

    @staticmethod
    def _nutrient_ph_recommendations(ph: float, thresholds: Optional[ThresholdMap] = None) -> list[Recommendation]:
        """pH recommendations — research basis: optimal 5.5-6.5 (Ngoc et al., 2024)."""
        recs: list[Recommendation] = []
        t_bounds = thresholds.get(PARAM_PH, {}) if thresholds else {}
        crit_hi = t_bounds.get("critical_max") or PH.critical_high
        warn_hi = t_bounds.get("warn_max") or PH.warn_high
        opt_hi = t_bounds.get("optimal_max") or PH.optimal_high
        opt_lo = t_bounds.get("optimal_min") or PH.optimal_low
        warn_lo = t_bounds.get("warn_min") or PH.warn_low
        crit_lo = t_bounds.get("critical_min") or PH.critical_low

        if ph <= crit_lo:
            recs.append(Recommendation(
                action="apply_lime_to_raise_ph",
                priority="critical",
                reason=(
                    f"pH {ph:.2f} is at critical low {crit_lo:.1f}. "
                    "Apply agricultural lime immediately — full Ca/Mg/P lock-out "
                    "is imminent at this acidity level."
                ),
                confidence=_confidence(ph, warn_lo, crit_lo),
            ))
        elif ph <= warn_lo:
            recs.append(Recommendation(
                action="apply_lime_to_raise_ph",
                priority="high",
                reason=(
                    f"pH {ph:.2f} is below warning low {warn_lo:.1f}. "
                    "Apply lime or dolomite to raise pH and restore P availability "
                    "(durian optimal pH: 5.5-6.5)."
                ),
                confidence=_confidence(ph, warn_lo, crit_lo),
            ))
        elif ph < opt_lo:
            recs.append(Recommendation(
                action="apply_lime_to_raise_ph",
                priority="medium",
                reason=(
                    f"pH {ph:.2f} is below optimal minimum {opt_lo:.1f}. "
                    "Schedule a lime application to return pH to optimal range "
                    "(research: durian optimal pH 5.5-6.5)."
                ),
                confidence=0.62,
            ))

        if ph >= crit_hi:
            recs.append(Recommendation(
                action="apply_sulfur_to_lower_ph",
                priority="critical",
                reason=(
                    f"pH {ph:.2f} is at critical high {crit_hi:.1f}. "
                    "Apply elemental sulfur or acidifying fertiliser urgently — "
                    "Fe/Zn/Mn lock-out is active (research: optimal pH ≤6.5)."
                ),
                confidence=_confidence(ph, warn_hi, crit_hi),
            ))
        elif ph >= warn_hi:
            recs.append(Recommendation(
                action="apply_sulfur_to_lower_ph",
                priority="high",
                reason=(
                    f"pH {ph:.2f} exceeds warning high {warn_hi:.1f}. "
                    "Apply sulfur-based acidifier to lower pH and restore "
                    "micronutrient availability (research: optimal pH ≤6.5)."
                ),
                confidence=_confidence(ph, warn_hi, crit_hi),
            ))
        elif ph > opt_hi:
            recs.append(Recommendation(
                action="apply_sulfur_to_lower_ph",
                priority="medium",
                reason=(
                    f"pH {ph:.2f} exceeds optimal maximum {opt_hi:.1f}. "
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
        thresholds: Optional[ThresholdMap] = None,
    ) -> list[Recommendation]:
        """Vapor Pressure Deficit recommendations.

        High VPD increases transpiration and accelerates soil moisture depletion.
        Recommendations target reducing evaporative load through cooling or misting.
        """
        recs: list[Recommendation] = []
        t_bounds = thresholds.get(PARAM_VPD, {}) if thresholds else {}
        crit_hi = t_bounds.get("critical_max") or VPD.critical_high
        warn_hi = t_bounds.get("warn_max") or VPD.warn_high

        if vpd >= crit_hi:
            recs.append(Recommendation(
                action="trigger_micro_sprinkler_cooling",
                priority="critical",
                reason=(
                    f"VPD {vpd:.2f} kPa (T={temperature:.1f} °C, H={humidity:.1f} %) "
                    f"exceeds critical {crit_hi:.1f} kPa — stomatal closure "
                    "and severe water stress are occurring even if soil moisture is "
                    "adequate. Activate misting/sprinkler to lower atmospheric demand."
                ),
                confidence=_confidence(vpd, warn_hi, crit_hi),
            ))
        elif vpd >= warn_hi:
            recs.append(Recommendation(
                action="trigger_micro_sprinkler_cooling",
                priority="high",
                reason=(
                    f"VPD {vpd:.2f} kPa (T={temperature:.1f} °C, H={humidity:.1f} %) "
                    f"exceeds warning {warn_hi:.1f} kPa — evaporative demand "
                    "is high; activate misting to reduce canopy stress."
                ),
                confidence=_confidence(vpd, warn_hi, crit_hi),
            ))

        return recs

    # ---------------------------------------------------------------- Phytophthora

    @staticmethod
    def _phytophthora_recommendations(
        temperature: float,
        humidity: float,
        thresholds: Optional[ThresholdMap] = None,
    ) -> list[Recommendation]:
        """Recommendations for Phytophthora disease risk.

        Triggered when warm temperature × high soil moisture create conditions
        that favour P. palmivora (Guest & Drenth, 2004).
        """
        recs: list[Recommendation] = []
        t_bounds = thresholds.get(PARAM_PHYTOPHTHORA, {}) if thresholds else {}
        opt_lo = t_bounds.get("optimal_min") or PHYTOPHTHORA.temp_favour_low
        opt_hi = t_bounds.get("optimal_max") or PHYTOPHTHORA.temp_favour_high
        crit_hi = t_bounds.get("critical_max") or PHYTOPHTHORA.moisture_critical
        warn_hi = t_bounds.get("warn_max") or PHYTOPHTHORA.moisture_warn

        temp_in_range = opt_lo <= temperature <= opt_hi

        if temp_in_range and humidity >= crit_hi:
            conf = _confidence(
                humidity,
                warn_hi,
                crit_hi,
            )
            recs.append(Recommendation(
                action="inspect_for_phytophthora",
                priority="critical",
                reason=(
                    f"Critical Phytophthora conditions: T={temperature:.1f} °C and "
                    f"soil moisture {humidity:.1f} % ≥ {crit_hi:.0f} %. "
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
        elif temp_in_range and humidity >= warn_hi:
            conf = _confidence(
                humidity,
                warn_hi,
                crit_hi,
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
        thresholds: Optional[ThresholdMap] = None,
    ) -> list[Recommendation]:
        """Multi-variable conditions that require a combined response."""
        recs: list[Recommendation] = []
        
        t_bounds_t = thresholds.get(PARAM_TEMPERATURE, {}) if thresholds else {}
        t_warn_hi = t_bounds_t.get("warn_max") or TEMPERATURE.warn_high
        t_opt_hi = t_bounds_t.get("optimal_max") or TEMPERATURE.optimal_high
        t_opt_lo = t_bounds_t.get("optimal_min") or TEMPERATURE.optimal_low
        
        t_bounds_h = thresholds.get(PARAM_HUMIDITY, {}) if thresholds else {}
        h_opt_lo = t_bounds_h.get("optimal_min") or HUMIDITY.optimal_low
        h_warn_lo = t_bounds_h.get("warn_min") or HUMIDITY.warn_low
        h_opt_hi = t_bounds_h.get("optimal_max") or HUMIDITY.optimal_high
        
        t_bounds_ec = thresholds.get(PARAM_EC, {}) if thresholds else {}
        ec_opt_lo = t_bounds_ec.get("optimal_min") or EC.optimal_low
        ec_opt_hi = t_bounds_ec.get("optimal_max") or EC.optimal_high
        
        t_bounds_ph = thresholds.get(PARAM_PH, {}) if thresholds else {}
        ph_opt_lo = t_bounds_ph.get("optimal_min") or PH.optimal_low
        ph_opt_hi = t_bounds_ph.get("optimal_max") or PH.optimal_high

        # Combined heat + drought: nutrient uptake collapses
        is_hot = temperature >= t_warn_hi
        is_dry = humidity < h_opt_lo
        if is_hot and is_dry:
            recs.append(Recommendation(
                action="reduce_fertigation_until_heat_stress_resolved",
                priority="high",
                reason=(
                    f"Combined heat ({temperature:.1f} °C) and drought "
                    f"({humidity:.1f} % < {h_opt_lo:.0f} % VWC). "
                    "Nutrient uptake is severely impaired at high temperature with "
                    "low soil moisture — reduce fertigation concentration to avoid "
                    "EC build-up during stress (research: nutrient uptake needs "
                    "adequate water flow through roots)."
                ),
                confidence=0.75,
            ))

        # Flowering trigger advisory — Eguchi et al. (2024): ~50 days after 15-day dry spell
        is_dry_for_flowering = humidity < h_warn_lo
        is_cool_enough = temperature <= t_opt_hi
        if is_dry_for_flowering and is_cool_enough:
            recs.append(Recommendation(
                action="anticipate_flowering_trigger",
                priority="low",
                reason=(
                    f"Dry-spell conditions detected: soil moisture {humidity:.1f} % "
                    f"< {h_warn_lo:.0f} % with T={temperature:.1f} °C. "
                    "If this persists for ~15 days, flowering initiation may begin "
                    "~50 days later (Eguchi et al., 2024). Schedule bud monitoring "
                    "and prepare pre-flowering nutrient program "
                    "(reduce N, maintain high K)."
                ),
                confidence=0.65,
            ))

        # Optimal conditions — positive reinforcement advisory
        temp_ok = t_opt_lo <= temperature <= t_opt_hi
        hum_ok = h_opt_lo <= humidity <= h_opt_hi
        ec_ok = ec_opt_lo <= ec <= ec_opt_hi
        ph_ok = ph_opt_lo <= ph <= ph_opt_hi
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
