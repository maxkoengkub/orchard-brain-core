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

from typing import TypedDict

from ._thresholds import (
    EC, HUMIDITY, PH, PHYTOPHTHORA, TEMPERATURE, VPD, compute_vpd_kpa,
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
    ) -> list[Risk]:
        """Return all active risks for the given sensor readings."""
        vpd = compute_vpd_kpa(temperature, humidity)

        risks: list[Risk] = []
        risks.extend(self._temperature_risks(temperature))
        risks.extend(self._humidity_risks(humidity))
        risks.extend(self._ec_risks(ec))
        risks.extend(self._ph_risks(ph))
        risks.extend(self._vpd_risks(vpd, temperature, humidity))
        risks.extend(self._phytophthora_risks(temperature, humidity))

        risks.sort(key=lambda r: (self._SEVERITY_ORDER[r["severity"]], r["risk"]))
        return risks

    # ----------------------------------------------------------------- internal

    @staticmethod
    def _temperature_risks(temperature: float) -> list[Risk]:
        risks: list[Risk] = []

        if temperature >= TEMPERATURE.critical_high:
            risks.append(Risk(
                risk="heat_stress",
                severity="critical",
                message=(
                    f"Temperature {temperature:.1f} °C exceeds critical high "
                    f"{TEMPERATURE.critical_high:.1f} °C — severe heat damage "
                    "and flower/fruit drop likely (Haifa Guide)."
                ),
            ))
        elif temperature >= TEMPERATURE.warn_high:
            risks.append(Risk(
                risk="heat_stress",
                severity="warning",
                message=(
                    f"Temperature {temperature:.1f} °C exceeds warning high "
                    f"{TEMPERATURE.warn_high:.1f} °C — heat stress is building; "
                    "consider cooling measures."
                ),
            ))

        if temperature <= TEMPERATURE.critical_low:
            risks.append(Risk(
                risk="cold_stress",
                severity="critical",
                message=(
                    f"Temperature {temperature:.1f} °C is at or below critical low "
                    f"{TEMPERATURE.critical_low:.1f} °C — chilling injury imminent."
                ),
            ))
        elif temperature <= TEMPERATURE.warn_low:
            risks.append(Risk(
                risk="cold_stress",
                severity="warning",
                message=(
                    f"Temperature {temperature:.1f} °C is at or below warning low "
                    f"{TEMPERATURE.warn_low:.1f} °C — growth slowdown and delayed "
                    "fruiting expected (research: <22 °C stunts durian growth)."
                ),
            ))

        return risks

    @staticmethod
    def _humidity_risks(humidity: float) -> list[Risk]:
        risks: list[Risk] = []

        if humidity <= HUMIDITY.critical_low:
            risks.append(Risk(
                risk="drought",
                severity="critical",
                message=(
                    f"Soil moisture {humidity:.1f} % is at or below critical low "
                    f"{HUMIDITY.critical_low:.1f} % — wilting and root collapse imminent."
                ),
            ))
        elif humidity <= HUMIDITY.warn_low:
            risks.append(Risk(
                risk="drought",
                severity="warning",
                message=(
                    f"Soil moisture {humidity:.1f} % is below warning low "
                    f"{HUMIDITY.warn_low:.1f} % — severe drought stress; "
                    "irrigation required."
                ),
            ))
        elif humidity < HUMIDITY.optimal_low:
            risks.append(Risk(
                risk="drought",
                severity="warning",
                message=(
                    f"Soil moisture {humidity:.1f} % is below optimal minimum "
                    f"{HUMIDITY.optimal_low:.1f} % VWC — mild moisture deficit "
                    "(FAO optimal: 40-60 % VWC)."
                ),
            ))

        if humidity >= HUMIDITY.critical_high:
            risks.append(Risk(
                risk="waterlogging",
                severity="critical",
                message=(
                    f"Soil moisture {humidity:.1f} % is at or above critical high "
                    f"{HUMIDITY.critical_high:.1f} % — root anaerobia and "
                    "Phytophthora conditions are critical."
                ),
            ))
        elif humidity >= HUMIDITY.warn_high:
            risks.append(Risk(
                risk="waterlogging",
                severity="warning",
                message=(
                    f"Soil moisture {humidity:.1f} % exceeds warning high "
                    f"{HUMIDITY.warn_high:.1f} % — waterlogging risk; stop "
                    "irrigation and check drainage."
                ),
            ))
        elif humidity > HUMIDITY.optimal_high:
            risks.append(Risk(
                risk="waterlogging",
                severity="warning",
                message=(
                    f"Soil moisture {humidity:.1f} % exceeds optimal maximum "
                    f"{HUMIDITY.optimal_high:.1f} % — monitor for waterlogging "
                    "(FAO optimal: 40-60 % VWC)."
                ),
            ))

        return risks

    @staticmethod
    def _ec_risks(ec: float) -> list[Risk]:
        risks: list[Risk] = []

        if ec <= EC.critical_low:
            risks.append(Risk(
                risk="nutrient_deficiency",
                severity="critical",
                message=(
                    f"EC {ec:.0f} µS/cm is at or below critical low "
                    f"{EC.critical_low:.0f} µS/cm — severe nutrient starvation "
                    "(Tang et al., 2024: balanced NPK is critical for yield)."
                ),
            ))
        elif ec <= EC.warn_low:
            risks.append(Risk(
                risk="nutrient_deficiency",
                severity="warning",
                message=(
                    f"EC {ec:.0f} µS/cm is below warning low "
                    f"{EC.warn_low:.0f} µS/cm — nutrient deficiency developing."
                ),
            ))
        elif ec < EC.optimal_low:
            risks.append(Risk(
                risk="nutrient_deficiency",
                severity="warning",
                message=(
                    f"EC {ec:.0f} µS/cm is below optimal minimum "
                    f"{EC.optimal_low:.0f} µS/cm — consider fertigation adjustment."
                ),
            ))

        if ec >= EC.critical_high:
            risks.append(Risk(
                risk="nutrient_toxicity",
                severity="critical",
                message=(
                    f"EC {ec:.0f} µS/cm is at or above critical high "
                    f"{EC.critical_high:.0f} µS/cm — salt toxicity causing root burn."
                ),
            ))
        elif ec >= EC.warn_high:
            risks.append(Risk(
                risk="nutrient_toxicity",
                severity="warning",
                message=(
                    f"EC {ec:.0f} µS/cm exceeds warning high "
                    f"{EC.warn_high:.0f} µS/cm — salt stress; leaching recommended."
                ),
            ))
        elif ec > EC.optimal_high:
            risks.append(Risk(
                risk="nutrient_toxicity",
                severity="warning",
                message=(
                    f"EC {ec:.0f} µS/cm exceeds optimal maximum "
                    f"{EC.optimal_high:.0f} µS/cm — monitor salt accumulation."
                ),
            ))

        return risks

    @staticmethod
    def _ph_risks(ph: float) -> list[Risk]:
        """pH risk assessment — research basis: optimal 5.5-6.5 (Ngoc et al., 2024)."""
        risks: list[Risk] = []

        if ph <= PH.critical_low:
            risks.append(Risk(
                risk="ph_acid",
                severity="critical",
                message=(
                    f"pH {ph:.2f} is at or below critical low {PH.critical_low:.1f} "
                    "— severe acid toxicity; Ca/Mg/P lock-out imminent."
                ),
            ))
        elif ph <= PH.warn_low:
            risks.append(Risk(
                risk="ph_acid",
                severity="warning",
                message=(
                    f"pH {ph:.2f} is below warning low {PH.warn_low:.1f} "
                    "— Mn/Fe toxicity and P lock-out risk "
                    "(research: pH optimum 5.5-6.5)."
                ),
            ))
        elif ph < PH.optimal_low:
            risks.append(Risk(
                risk="ph_acid",
                severity="warning",
                message=(
                    f"pH {ph:.2f} is below optimal minimum {PH.optimal_low:.1f} "
                    "— mild acidic drift; monitor nutrient uptake."
                ),
            ))

        if ph >= PH.critical_high:
            risks.append(Risk(
                risk="ph_alkaline",
                severity="critical",
                message=(
                    f"pH {ph:.2f} is at or above critical high {PH.critical_high:.1f} "
                    "— Fe/Zn/Mn lock-out; urgent pH correction needed."
                ),
            ))
        elif ph >= PH.warn_high:
            risks.append(Risk(
                risk="ph_alkaline",
                severity="warning",
                message=(
                    f"pH {ph:.2f} exceeds warning high {PH.warn_high:.1f} "
                    "— alkaline drift reducing micronutrient availability "
                    "(research: optimal upper limit 6.5)."
                ),
            ))
        elif ph > PH.optimal_high:
            risks.append(Risk(
                risk="ph_alkaline",
                severity="warning",
                message=(
                    f"pH {ph:.2f} exceeds optimal maximum {PH.optimal_high:.1f} "
                    "— early alkaline drift; monitor and apply acidifier if it rises "
                    "(research: durian optimal pH 5.5-6.5)."
                ),
            ))

        return risks

    @staticmethod
    def _vpd_risks(vpd: float, temperature: float, humidity: float) -> list[Risk]:
        """Vapor Pressure Deficit risks — atmospheric drought demand.

        VPD = es × (1 − RH/100), where es is saturation vapor pressure.
        High VPD means the atmosphere can absorb much more water from leaves,
        increasing transpiration and accelerating soil moisture depletion.
        """
        risks: list[Risk] = []

        if vpd >= VPD.critical_high:
            risks.append(Risk(
                risk="vpd_stress",
                severity="critical",
                message=(
                    f"VPD {vpd:.2f} kPa (T={temperature:.1f} °C, "
                    f"H={humidity:.1f} %) exceeds critical {VPD.critical_high:.1f} kPa "
                    "— severe atmospheric drought demand; stomata closing and "
                    "water uptake is compromised even in moist soil."
                ),
            ))
        elif vpd >= VPD.warn_high:
            risks.append(Risk(
                risk="vpd_stress",
                severity="warning",
                message=(
                    f"VPD {vpd:.2f} kPa (T={temperature:.1f} °C, "
                    f"H={humidity:.1f} %) exceeds warning {VPD.warn_high:.1f} kPa "
                    "— elevated evaporative demand; water stress building."
                ),
            ))

        return risks

    @staticmethod
    def _phytophthora_risks(temperature: float, humidity: float) -> list[Risk]:
        """Phytophthora palmivora disease risk.

        Research (Guest & Drenth, 2004): P. palmivora thrives in warm (25-35 °C),
        persistently wet soil.  High EC / excess inorganic N raises infection risk.
        We detect the environment (temperature × soil moisture) as a proxy.
        """
        risks: list[Risk] = []

        temp_in_range = PHYTOPHTHORA.temp_favour_low <= temperature <= PHYTOPHTHORA.temp_favour_high

        if temp_in_range and humidity >= PHYTOPHTHORA.moisture_critical:
            risks.append(Risk(
                risk="phytophthora_risk",
                severity="critical",
                message=(
                    f"Critical Phytophthora risk: T={temperature:.1f} °C in pathogen "
                    f"optimal range and soil moisture {humidity:.1f} % ≥ critical wet "
                    f"threshold {PHYTOPHTHORA.moisture_critical:.0f} %. "
                    "Inspect trees for root/stem canker; apply fungicide preventatively "
                    "(Guest & Drenth, 2004)."
                ),
            ))
        elif temp_in_range and humidity >= PHYTOPHTHORA.moisture_warn:
            risks.append(Risk(
                risk="phytophthora_risk",
                severity="warning",
                message=(
                    f"Phytophthora-favourable conditions: T={temperature:.1f} °C and "
                    f"soil moisture {humidity:.1f} % ≥ {PHYTOPHTHORA.moisture_warn:.0f} %. "
                    "Improve drainage and apply preventative mulch to reduce infection risk."
                ),
            ))

        return risks
