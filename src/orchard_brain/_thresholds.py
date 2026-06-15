"""Durian-specific agronomic thresholds — single source of truth.

All values are grounded in peer-reviewed durian cultivation research:
  - Haifa Group Durian Guide (optimal climate 25-32 °C, 75-85 % RH)
  - Ngoc et al. (2024) — leaf nutrient optimal ranges
  - Tang et al. (2024) — soil nutrient & EC management
  - Eguchi et al. (2024) — flowering dry-spell trigger (~15 days)
  - Guest & Drenth (2004) — Phytophthora management
  - FAO / extension manuals — soil pH 5.5-6.5, VWC 40-60 %

Modifying this file is the only change required to update decision
boundaries across all three assessors.  All units and conversions are
documented inline.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class _TemperatureThresholds:
    """Air temperature in °C.

    Research basis:
      Optimal daytime temperature: 25-32 °C.
      Below 22 °C stunts growth and delays fruiting (Haifa Guide).
      Extreme heat >38-40 °C causes leaf scorch and fruit drop.
    """
    optimal_low: float = 25.0    # °C
    optimal_high: float = 32.0   # °C
    warn_low: float = 22.0       # °C  — growth slowdown (was 20 °C; corrected from research)
    warn_high: float = 35.0      # °C  — heat stress onset
    critical_low: float = 15.0   # °C  — chilling injury risk
    critical_high: float = 38.0  # °C  — severe heat / flower drop threshold


@dataclass(frozen=True)
class _HumidityThresholds:
    """Relative humidity (%) used as soil-moisture proxy until dedicated VWC
    probes are deployed (see RulesEngine comment in rules_engine.py).

    Research basis (soil VWC mapping):
      Well-watered: 40-60 % VWC (Haifa Guide / FAO).
      Drought stress: <30 % VWC; severe drought <20 % VWC.
      Waterlogging: >75 % (Phytophthora risk), critical >85 %.
    """
    optimal_low: float = 40.0   # %   — below this, drought stress begins
    optimal_high: float = 60.0  # %   — above this, waterlogging risk
    warn_low: float = 25.0      # %   — drought warning zone (20-30 % VWC)
    warn_high: float = 75.0     # %   — waterlogging / Phytophthora warning
    critical_low: float = 10.0  # %   — wilting / root collapse imminent
    critical_high: float = 85.0 # %   — root anaerobia; severe Phytophthora risk


@dataclass(frozen=True)
class _ECThresholds:
    """Electrical conductivity of fertigation/irrigation solution (µS/cm).

    Note on units: agronomic literature often cites soil EC in dS/m.
    1 dS/m = 1000 µS/cm.  Sensor readings in this system are in µS/cm
    for the fertigation solution; healthy solution range ≈ 150-300 µS/cm.
    Soil bulk EC (<2000 µS/cm = <2 dS/m) is not directly read here.
    """
    optimal_low: float = 150.0   # µS/cm — below this, nutrient deficiency
    optimal_high: float = 300.0  # µS/cm — above this, salt build-up risk
    warn_low: float = 100.0      # µS/cm — nutrient deficiency warning
    warn_high: float = 400.0     # µS/cm — mild salt stress
    critical_low: float = 50.0   # µS/cm — severe nutrient starvation
    critical_high: float = 600.0 # µS/cm — salt toxicity / root burn


@dataclass(frozen=True)
class _PHThresholds:
    """Soil pH — governs macronutrient and micronutrient availability.

    Research basis:
      Durian prefers mildly acidic soil: pH 5.5-6.5 (Haifa Guide / FAO).
      Below pH 5.0: Ca and Mg deficiency, Mn/Fe toxicity.
      Above pH 7.0: Fe, Zn, Mn deficiency (alkaline lock-out).
      Irrigation water target: pH 6.0-7.5.
    """
    optimal_low: float = 5.5    # — below: P lock-out, Mn/Fe toxicity
    optimal_high: float = 6.5   # — above: micronutrient availability falls (was 7.0; corrected)
    warn_low: float = 5.0       # — warning: strong acidity
    warn_high: float = 7.0      # — warning: alkaline drift (was 7.5; corrected)
    critical_low: float = 4.5   # — critical: severe acid toxicity
    critical_high: float = 7.5  # — critical: near-complete nutrient lock-out (was 8.0; corrected)


@dataclass(frozen=True)
class _VPDThresholds:
    """Vapor Pressure Deficit (kPa) — derived from air temperature and RH.

    VPD quantifies the evaporative demand of the atmosphere.  High VPD
    increases transpiration, accelerates soil moisture depletion, and
    predicts drought stress before soil moisture sensors respond.

    Durian context:
      Comfortable: VPD < 2.0 kPa (tropical humid conditions).
      Stress onset: VPD > 3.0 kPa (stomata start to close).
      Critical: VPD > 4.0 kPa (severe water stress even in moist soil).
    """
    optimal_high: float = 2.0   # kPa — comfortable evaporative demand
    warn_high: float = 3.0      # kPa — water stress building
    critical_high: float = 4.0  # kPa — severe atmospheric drought stress


@dataclass(frozen=True)
class _PhytophthoraThresholds:
    """Conditions that favour Phytophthora palmivora (root/stem rot).

    Research basis (Guest & Drenth, 2004):
      P. palmivora thrives at 25-35 °C with persistently wet soil.
      Excess inorganic N raises infection risk.
      Risk is triggered by the combination of warm temperatures and
      high soil moisture (which we observe via the humidity proxy).
    """
    temp_favour_low: float = 25.0    # °C — warm enough to favour pathogen
    temp_favour_high: float = 35.0   # °C — above this, pathogen growth slows
    moisture_warn: float = 70.0      # % — moist enough for warning-level risk
    moisture_critical: float = 80.0  # % — critical infection risk


# ── Singletons (import these; do not instantiate the classes directly)
TEMPERATURE = _TemperatureThresholds()
HUMIDITY = _HumidityThresholds()
EC = _ECThresholds()
PH = _PHThresholds()
VPD = _VPDThresholds()
PHYTOPHTHORA = _PhytophthoraThresholds()


# ── Utility: VPD calculation (Tetens / Magnus formula)
def compute_vpd_kpa(temperature: float, humidity: float) -> float:
    """Return Vapor Pressure Deficit in kPa.

    Args:
        temperature: Air temperature in °C.
        humidity:    Relative humidity in % (0-100).

    Returns:
        VPD in kPa (non-negative).
    """
    # Saturation vapor pressure — Magnus approximation (kPa)
    es = 0.6108 * math.exp(17.27 * temperature / (temperature + 237.3))
    ea = es * max(0.0, min(100.0, humidity)) / 100.0
    return max(0.0, es - ea)
