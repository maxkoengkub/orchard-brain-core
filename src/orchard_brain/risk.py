"""RiskAssessment — identifies agronomic risks from sensor readings.

Each risk is a plain dict so it serialises directly to JSON with no extra
dependencies.  Severity levels follow a two-tier model:

  "warning"  — condition is outside the optimal range but within safe limits;
               operator attention required within hours.
  "critical" — condition has exceeded safe limits; immediate action required.

Risk identifiers
────────────────
  heat_stress          temperature above warning/critical high threshold
  cold_stress          temperature below warning/critical low threshold
  drought              humidity (soil moisture proxy) below thresholds
  waterlogging         humidity above thresholds; root oxygen depletion
  nutrient_deficiency  EC below warning/critical low threshold
  nutrient_toxicity    EC above warning/critical high threshold
  ph_acid              pH below warning/critical low threshold (research: <5.5 optimal)
  ph_alkaline          pH above warning/critical high threshold (research: >6.5 optimal)
  vpd_stress           Vapor Pressure Deficit exceeds comfortable range
  phytophthora_risk    warm + wet conditions favour P. palmivora infection
                       (Guest & Drenth, 2004)

Output format per risk item:
  {
      "risk":     str,   # identifier from the list above
      "severity": str,   # "warning" | "critical"
      "message":  str,   # human-readable explanation with actual values
  }
"""
from __future__ import annotations

from typing import TypedDict, Optional

from ._thresholds import (
    EC, HUMIDITY, PH, PHYTOPHTHORA, TEMPERATURE, VPD, compute_vpd_kpa,
)
from .knowledge.threshold_engine import (
    ThresholdMap,
    PARAM_TEMPERATURE,
    PARAM_HUMIDITY,
    PARAM_EC,
    PARAM_PH,
    PARAM_VPD,
    PARAM_PHYTOPHTHORA
)

class Risk(TypedDict):
    risk: str
    severity: str
    message: str


class RiskAssessment:
    """Stateless assessor — call ``assess(temperature, humidity, ec, ph)``.

    Returns a (possibly empty) list of ``Risk`` dicts sorted by severity
    (critical first) then by risk identifier for deterministic ordering.
    """

    _SEVERITY_ORDER = {"critical": 0, "warning": 1}

    # ---------------------------------------------------------------------- API

    def assess(
        self,
        temperature: float,
        humidity: float,
        ec: float,
        ph: float,
        thresholds: Optional[ThresholdMap] = None,
    ) -> list[Risk]:
        """Return all active risks for the given sensor readings."""
        vpd = compute_vpd_kpa(temperature, humidity)

        risks: list[Risk] = []
        risks.extend(self._temperature_risks(temperature, thresholds))
        risks.extend(self._humidity_risks(humidity, thresholds))
        risks.extend(self._ec_risks(ec, thresholds))
        risks.extend(self._ph_risks(ph, thresholds))
        risks.extend(self._vpd_risks(vpd, temperature, humidity, thresholds))
        risks.extend(self._phytophthora_risks(temperature, humidity, thresholds))

        risks.sort(key=lambda r: (self._SEVERITY_ORDER[r["severity"]], r["risk"]))
        return risks

    # ----------------------------------------------------------------- internal

    @staticmethod
    def _temperature_risks(temperature: float, thresholds: Optional[ThresholdMap] = None) -> list[Risk]:
        risks: list[Risk] = []
        t_bounds = thresholds.get(PARAM_TEMPERATURE, {}) if thresholds else {}
        crit_hi = t_bounds.get("critical_max") or TEMPERATURE.critical_high
        warn_hi = t_bounds.get("warn_max") or TEMPERATURE.warn_high
        crit_lo = t_bounds.get("critical_min") or TEMPERATURE.critical_low
        warn_lo = t_bounds.get("warn_min") or TEMPERATURE.warn_low

        if temperature >= crit_hi:
            risks.append(Risk(
                risk="heat_stress",
                severity="critical",
                message=(
                    f"Temperature {temperature:.1f} °C exceeds critical high "
                    f"{crit_hi:.1f} °C — severe heat damage "
                    "and flower/fruit drop likely (Haifa Guide)."
                ),
            ))
        elif temperature >= warn_hi:
            risks.append(Risk(
                risk="heat_stress",
                severity="warning",
                message=(
                    f"Temperature {temperature:.1f} °C exceeds warning high "
                    f"{warn_hi:.1f} °C — heat stress is building; "
                    "consider cooling measures."
                ),
            ))

        if temperature <= crit_lo:
            risks.append(Risk(
                risk="cold_stress",
                severity="critical",
                message=(
                    f"Temperature {temperature:.1f} °C is at or below critical low "
                    f"{crit_lo:.1f} °C — chilling injury imminent."
                ),
            ))
        elif temperature <= warn_lo:
            risks.append(Risk(
                risk="cold_stress",
                severity="warning",
                message=(
                    f"Temperature {temperature:.1f} °C is at or below warning low "
                    f"{warn_lo:.1f} °C — growth slowdown and delayed "
                    "fruiting expected (research: <22 °C stunts durian growth)."
                ),
            ))

        return risks

    @staticmethod
    def _humidity_risks(humidity: float, thresholds: Optional[ThresholdMap] = None) -> list[Risk]:
        risks: list[Risk] = []
        t_bounds = thresholds.get(PARAM_HUMIDITY, {}) if thresholds else {}
        crit_hi = t_bounds.get("critical_max") or HUMIDITY.critical_high
        warn_hi = t_bounds.get("warn_max") or HUMIDITY.warn_high
        opt_hi = t_bounds.get("optimal_max") or HUMIDITY.optimal_high
        opt_lo = t_bounds.get("optimal_min") or HUMIDITY.optimal_low
        warn_lo = t_bounds.get("warn_min") or HUMIDITY.warn_low
        crit_lo = t_bounds.get("critical_min") or HUMIDITY.critical_low

        if humidity <= crit_lo:
            risks.append(Risk(
                risk="drought",
                severity="critical",
                message=(
                    f"Soil moisture {humidity:.1f} % is at or below critical low "
                    f"{crit_lo:.1f} % — wilting and root collapse imminent."
                ),
            ))
        elif humidity <= warn_lo:
            risks.append(Risk(
                risk="drought",
                severity="warning",
                message=(
                    f"Soil moisture {humidity:.1f} % is below warning low "
                    f"{warn_lo:.1f} % — severe drought stress; "
                    "irrigation required."
                ),
            ))
        elif humidity < opt_lo:
            risks.append(Risk(
                risk="drought",
                severity="warning",
                message=(
                    f"Soil moisture {humidity:.1f} % is below optimal minimum "
                    f"{opt_lo:.1f} % VWC — mild moisture deficit "
                    "(FAO optimal: 40-60 % VWC)."
                ),
            ))

        if humidity >= crit_hi:
            risks.append(Risk(
                risk="waterlogging",
                severity="critical",
                message=(
                    f"Soil moisture {humidity:.1f} % is at or above critical high "
                    f"{crit_hi:.1f} % — root anaerobia and "
                    "Phytophthora conditions are critical."
                ),
            ))
        elif humidity >= warn_hi:
            risks.append(Risk(
                risk="waterlogging",
                severity="warning",
                message=(
                    f"Soil moisture {humidity:.1f} % exceeds warning high "
                    f"{warn_hi:.1f} % — waterlogging risk; stop "
                    "irrigation and check drainage."
                ),
            ))
        elif humidity > opt_hi:
            risks.append(Risk(
                risk="waterlogging",
                severity="warning",
                message=(
                    f"Soil moisture {humidity:.1f} % exceeds optimal maximum "
                    f"{opt_hi:.1f} % — monitor for waterlogging "
                    "(FAO optimal: 40-60 % VWC)."
                ),
            ))

        return risks

    @staticmethod
    def _ec_risks(ec: float, thresholds: Optional[ThresholdMap] = None) -> list[Risk]:
        risks: list[Risk] = []
        t_bounds = thresholds.get(PARAM_EC, {}) if thresholds else {}
        crit_hi = t_bounds.get("critical_max") or EC.critical_high
        warn_hi = t_bounds.get("warn_max") or EC.warn_high
        opt_hi = t_bounds.get("optimal_max") or EC.optimal_high
        opt_lo = t_bounds.get("optimal_min") or EC.optimal_low
        warn_lo = t_bounds.get("warn_min") or EC.warn_low
        crit_lo = t_bounds.get("critical_min") or EC.critical_low

        if ec <= crit_lo:
            risks.append(Risk(
                risk="nutrient_deficiency",
                severity="critical",
                message=(
                    f"EC {ec:.0f} µS/cm is at or below critical low "
                    f"{crit_lo:.0f} µS/cm — severe nutrient starvation "
                    "(Tang et al., 2024: balanced NPK is critical for yield)."
                ),
            ))
        elif ec <= warn_lo:
            risks.append(Risk(
                risk="nutrient_deficiency",
                severity="warning",
                message=(
                    f"EC {ec:.0f} µS/cm is below warning low "
                    f"{warn_lo:.0f} µS/cm — nutrient deficiency developing."
                ),
            ))
        elif ec < opt_lo:
            risks.append(Risk(
                risk="nutrient_deficiency",
                severity="warning",
                message=(
                    f"EC {ec:.0f} µS/cm is below optimal minimum "
                    f"{opt_lo:.0f} µS/cm — consider fertigation adjustment."
                ),
            ))

        if ec >= crit_hi:
            risks.append(Risk(
                risk="nutrient_toxicity",
                severity="critical",
                message=(
                    f"EC {ec:.0f} µS/cm is at or above critical high "
                    f"{crit_hi:.0f} µS/cm — salt toxicity causing root burn."
                ),
            ))
        elif ec >= warn_hi:
            risks.append(Risk(
                risk="nutrient_toxicity",
                severity="warning",
                message=(
                    f"EC {ec:.0f} µS/cm exceeds warning high "
                    f"{warn_hi:.0f} µS/cm — salt stress; leaching recommended."
                ),
            ))
        elif ec > opt_hi:
            risks.append(Risk(
                risk="nutrient_toxicity",
                severity="warning",
                message=(
                    f"EC {ec:.0f} µS/cm exceeds optimal maximum "
                    f"{opt_hi:.0f} µS/cm — monitor salt accumulation."
                ),
            ))

        return risks

    @staticmethod
    def _ph_risks(ph: float, thresholds: Optional[ThresholdMap] = None) -> list[Risk]:
        """pH risk assessment — research basis: optimal 5.5-6.5 (Ngoc et al., 2024)."""
        risks: list[Risk] = []
        t_bounds = thresholds.get(PARAM_PH, {}) if thresholds else {}
        crit_hi = t_bounds.get("critical_max") or PH.critical_high
        warn_hi = t_bounds.get("warn_max") or PH.warn_high
        opt_hi = t_bounds.get("optimal_max") or PH.optimal_high
        opt_lo = t_bounds.get("optimal_min") or PH.optimal_low
        warn_lo = t_bounds.get("warn_min") or PH.warn_low
        crit_lo = t_bounds.get("critical_min") or PH.critical_low

        if ph <= crit_lo:
            risks.append(Risk(
                risk="ph_acid",
                severity="critical",
                message=(
                    f"pH {ph:.2f} is at or below critical low {crit_lo:.1f} "
                    "— severe acid toxicity; Ca/Mg/P lock-out imminent."
                ),
            ))
        elif ph <= warn_lo:
            risks.append(Risk(
                risk="ph_acid",
                severity="warning",
                message=(
                    f"pH {ph:.2f} is below warning low {warn_lo:.1f} "
                    "— Mn/Fe toxicity and P lock-out risk "
                    "(research: pH optimum 5.5-6.5)."
                ),
            ))
        elif ph < opt_lo:
            risks.append(Risk(
                risk="ph_acid",
                severity="warning",
                message=(
                    f"pH {ph:.2f} is below optimal minimum {opt_lo:.1f} "
                    "— mild acidic drift; monitor nutrient uptake."
                ),
            ))

        if ph >= crit_hi:
            risks.append(Risk(
                risk="ph_alkaline",
                severity="critical",
                message=(
                    f"pH {ph:.2f} is at or above critical high {crit_hi:.1f} "
                    "— Fe/Zn/Mn lock-out; urgent pH correction needed."
                ),
            ))
        elif ph >= warn_hi:
            risks.append(Risk(
                risk="ph_alkaline",
                severity="warning",
                message=(
                    f"pH {ph:.2f} exceeds warning high {warn_hi:.1f} "
                    "— alkaline drift reducing micronutrient availability "
                    "(research: optimal upper limit 6.5)."
                ),
            ))
        elif ph > opt_hi:
            risks.append(Risk(
                risk="ph_alkaline",
                severity="warning",
                message=(
                    f"pH {ph:.2f} exceeds optimal maximum {opt_hi:.1f} "
                    "— early alkaline drift; monitor and apply acidifier if it rises "
                    "(research: durian optimal pH 5.5-6.5)."
                ),
            ))

        return risks

    @staticmethod
    def _vpd_risks(vpd: float, temperature: float, humidity: float, thresholds: Optional[ThresholdMap] = None) -> list[Risk]:
        """Vapor Pressure Deficit risks — atmospheric drought demand.

        VPD = es × (1 − RH/100), where es is saturation vapor pressure.
        High VPD means the atmosphere can absorb much more water from leaves,
        increasing transpiration and accelerating soil moisture depletion.
        """
        risks: list[Risk] = []
        t_bounds = thresholds.get(PARAM_VPD, {}) if thresholds else {}
        crit_hi = t_bounds.get("critical_max") or VPD.critical_high
        warn_hi = t_bounds.get("warn_max") or VPD.warn_high

        if vpd >= crit_hi:
            risks.append(Risk(
                risk="vpd_stress",
                severity="critical",
                message=(
                    f"VPD {vpd:.2f} kPa (T={temperature:.1f} °C, "
                    f"H={humidity:.1f} %) exceeds critical {crit_hi:.1f} kPa "
                    "— severe atmospheric drought demand; stomata closing and "
                    "water uptake is compromised even in moist soil."
                ),
            ))
        elif vpd >= warn_hi:
            risks.append(Risk(
                risk="vpd_stress",
                severity="warning",
                message=(
                    f"VPD {vpd:.2f} kPa (T={temperature:.1f} °C, "
                    f"H={humidity:.1f} %) exceeds warning {warn_hi:.1f} kPa "
                    "— elevated evaporative demand; water stress building."
                ),
            ))

        return risks

    @staticmethod
    def _phytophthora_risks(temperature: float, humidity: float, thresholds: Optional[ThresholdMap] = None) -> list[Risk]:
        """Phytophthora palmivora disease risk.

        Research (Guest & Drenth, 2004): P. palmivora thrives in warm (25-35 °C),
        persistently wet soil.  High EC / excess inorganic N raises infection risk.
        We detect the environment (temperature × soil moisture) as a proxy.
        """
        risks: list[Risk] = []
        t_bounds = thresholds.get(PARAM_PHYTOPHTHORA, {}) if thresholds else {}
        opt_lo = t_bounds.get("optimal_min") or PHYTOPHTHORA.temp_favour_low
        opt_hi = t_bounds.get("optimal_max") or PHYTOPHTHORA.temp_favour_high
        crit_hi = t_bounds.get("critical_max") or PHYTOPHTHORA.moisture_critical
        warn_hi = t_bounds.get("warn_max") or PHYTOPHTHORA.moisture_warn

        temp_in_range = opt_lo <= temperature <= opt_hi

        if temp_in_range and humidity >= crit_hi:
            risks.append(Risk(
                risk="phytophthora_risk",
                severity="critical",
                message=(
                    f"Critical Phytophthora risk: T={temperature:.1f} °C in pathogen "
                    f"optimal range and soil moisture {humidity:.1f} % ≥ critical wet "
                    f"threshold {crit_hi:.0f} %. "
                    "Inspect trees for root/stem canker; apply fungicide preventatively "
                    "(Guest & Drenth, 2004)."
                ),
            ))
        elif temp_in_range and humidity >= warn_hi:
            risks.append(Risk(
                risk="phytophthora_risk",
                severity="warning",
                message=(
                    f"Phytophthora-favourable conditions: T={temperature:.1f} °C and "
                    f"soil moisture {humidity:.1f} % ≥ {warn_hi:.0f} %. "
                    "Improve drainage and apply preventative mulch to reduce infection risk."
                ),
            ))

        return risks
