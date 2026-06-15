"""Phase 2 — Causal Reasoning Engine.

Converts observed sensor readings + trend data into structured causal chains::

    Low soil moisture
    → High VPD
    → Water stress
    → Fruit drop risk
    → Irrigation recommendation

Each CausalChain has: cause, impact, risk, action, confidence.
The engine wires chains together from a library of known agronomic pathways.
"""
from __future__ import annotations

from dataclasses import dataclass

from ._thresholds import (
    EC, HUMIDITY, PH, PHYTOPHTHORA, TEMPERATURE, VPD, compute_vpd_kpa,
)


# ─────────────────────────────────────────────────── data structure


@dataclass(frozen=True)
class CausalChain:
    """A single cause-to-action reasoning path.

    All fields are human-readable strings so the chain can be serialised
    directly to the explainable report without further transformation.
    """
    cause: str       # what the sensor or trend shows
    impact: str      # physiological / ecological effect
    risk: str        # crop outcome at stake
    action: str      # recommended management response
    confidence: float  # 0.0 – 1.0


# ─────────────────────────────────────────────────── engine


class CausalEngine:
    """Build reasoning chains for the current orchard state.

    Call ``build_reasoning_chain(observations)`` where ``observations`` is
    a dict with keys: temperature, humidity (soil moisture), ec, ph,
    vpd_kpa (optional — computed if absent), and optionally trend names
    (list[str]).
    """

    def build_reasoning_chain(self, observations: dict) -> list[CausalChain]:
        """Return all causal chains triggered by ``observations``.

        Chains are ordered from highest to lowest confidence.
        """
        T = float(observations.get("temperature", 28.0))
        H = float(observations.get("humidity", 50.0))
        EC_val = float(observations.get("ec", 220.0))
        PH_val = float(observations.get("ph", 6.0))
        vpd = float(observations.get("vpd_kpa", compute_vpd_kpa(T, H)))
        trends: list[str] = list(observations.get("trends", []))

        chains: list[CausalChain] = []

        chains.extend(self._drought_chains(H, vpd))
        chains.extend(self._waterlogging_chains(H, T))
        chains.extend(self._heat_chains(T, vpd))
        chains.extend(self._cold_chains(T))
        chains.extend(self._nutrient_ec_chains(EC_val))
        chains.extend(self._ph_chains(PH_val))
        chains.extend(self._phytophthora_chains(T, H))
        chains.extend(self._vpd_chains(vpd, T, H))
        chains.extend(self._trend_chains(trends, H, T))

        chains.sort(key=lambda c: -c.confidence)
        return chains

    # ──────────────────────────────────────── drought pathway

    @staticmethod
    def _drought_chains(humidity: float, vpd: float) -> list[CausalChain]:
        chains: list[CausalChain] = []

        if humidity < HUMIDITY.critical_low:
            chains.append(CausalChain(
                cause=f"Critical soil moisture deficit ({humidity:.1f} % < {HUMIDITY.critical_low:.0f} % VWC)",
                impact="Root water uptake fails — stomata close, photosynthesis halts, turgor lost",
                risk="Irreversible wilting and fruit drop within hours",
                action="Trigger irrigation immediately at maximum rate",
                confidence=0.97,
            ))
        elif humidity < HUMIDITY.warn_low:
            chains.append(CausalChain(
                cause=f"Soil moisture below warning threshold ({humidity:.1f} % < {HUMIDITY.warn_low:.0f} % VWC)",
                impact="Reduced water uptake — leaf temperature rises, VPD amplified at canopy level",
                risk="Fruit stress and premature drop if not corrected within 24 h",
                action="Trigger irrigation (high priority) and monitor soil recovery",
                confidence=0.85,
            ))
        elif humidity < HUMIDITY.optimal_low:
            chains.append(CausalChain(
                cause=f"Soil moisture below optimal range ({humidity:.1f} % < {HUMIDITY.optimal_low:.0f} % VWC)",
                impact="Sub-optimal water supply — transpiration deficit suppresses nutrient transport",
                risk="Mild growth slowdown and yield reduction if sustained",
                action="Schedule irrigation in the next cycle to return to 40-60 % VWC",
                confidence=0.70,
            ))

        if vpd >= VPD.warn_high and humidity < HUMIDITY.optimal_low:
            chains.append(CausalChain(
                cause=f"High VPD ({vpd:.2f} kPa) combined with low soil moisture ({humidity:.1f} %)",
                impact="Atmospheric and soil demand both pull water from plant simultaneously",
                risk="Compound water stress — leaf scorch and fruit drop accelerate",
                action="Activate misting AND irrigation together to break the stress loop",
                confidence=min(0.95, 0.75 + (vpd - VPD.warn_high) * 0.05),
            ))

        return chains

    # ──────────────────────────────────────── waterlogging pathway

    @staticmethod
    def _waterlogging_chains(humidity: float, temperature: float) -> list[CausalChain]:
        chains: list[CausalChain] = []

        if humidity >= HUMIDITY.critical_high:
            chains.append(CausalChain(
                cause=f"Critical waterlogging ({humidity:.1f} % ≥ {HUMIDITY.critical_high:.0f} % VWC)",
                impact="Root zone is anaerobic — root respiration impossible, ethylene accumulates",
                risk="Root death and systemic Phytophthora infection within 24-48 h",
                action="Stop all irrigation; open drainage; apply phosphonate fungicide",
                confidence=0.96,
            ))
        elif humidity >= HUMIDITY.warn_high:
            chains.append(CausalChain(
                cause=f"Waterlogging warning ({humidity:.1f} % ≥ {HUMIDITY.warn_high:.0f} % VWC)",
                impact="Poor aeration suppresses mycorrhizal activity; root disease pressure rises",
                risk="Root rot onset; Phytophthora spore germination triggered by standing water",
                action="Stop irrigation; check drainage channels; mulch to reduce surface wetness",
                confidence=0.80,
            ))

        return chains

    # ──────────────────────────────────────── heat pathway

    @staticmethod
    def _heat_chains(temperature: float, vpd: float) -> list[CausalChain]:
        chains: list[CausalChain] = []

        if temperature >= TEMPERATURE.critical_high:
            chains.append(CausalChain(
                cause=f"Extreme heat ({temperature:.1f} °C ≥ {TEMPERATURE.critical_high:.0f} °C)",
                impact="Protein denaturation in pollen; photosynthetic enzyme inactivation",
                risk="Flower abortion and total fruit drop — critical yield loss",
                action="Activate micro-sprinkler cooling immediately; increase irrigation frequency",
                confidence=0.95,
            ))
        elif temperature >= TEMPERATURE.warn_high:
            chains.append(CausalChain(
                cause=f"Heat stress ({temperature:.1f} °C ≥ {TEMPERATURE.warn_high:.0f} °C)",
                impact=f"High VPD ({vpd:.2f} kPa) accelerates transpiration beyond root supply capacity",
                risk="Leaf scorch and early fruit drop; reduced photosynthesis",
                action="Start micro-sprinkler cooling; reduce fertigation concentration",
                confidence=0.82,
            ))

        return chains

    # ──────────────────────────────────────── cold pathway

    @staticmethod
    def _cold_chains(temperature: float) -> list[CausalChain]:
        chains: list[CausalChain] = []

        if temperature <= TEMPERATURE.critical_low:
            chains.append(CausalChain(
                cause=f"Chilling temperature ({temperature:.1f} °C ≤ {TEMPERATURE.critical_low:.0f} °C)",
                impact="Membrane lipid solidification in roots and leaves — cell damage",
                risk="Irreversible chilling injury; delayed flowering and stunted growth",
                action="Apply frost protection covers; close greenhouse vents if applicable",
                confidence=0.93,
            ))
        elif temperature <= TEMPERATURE.warn_low:
            chains.append(CausalChain(
                cause=f"Below-optimal temperature ({temperature:.1f} °C ≤ {TEMPERATURE.warn_low:.0f} °C)",
                impact="Enzymatic reactions slow — nutrient uptake and cell division impaired",
                risk="Delayed fruiting and reduced shoot growth (research: <22 °C stunts durian)",
                action="Prepare protective measures; monitor night temperatures closely",
                confidence=0.75,
            ))

        return chains

    # ──────────────────────────────────────── EC pathway

    @staticmethod
    def _nutrient_ec_chains(ec: float) -> list[CausalChain]:
        chains: list[CausalChain] = []

        if ec <= EC.critical_low:
            chains.append(CausalChain(
                cause=f"Critically low nutrient solution EC ({ec:.0f} µS/cm ≤ {EC.critical_low:.0f} µS/cm)",
                impact="Insufficient mineral supply — N, P, K, Ca, Mg deficiency cascade",
                risk="Leaf yellowing, stunted growth, poor fruit set and low yield",
                action="Apply high-PK fertigation immediately (Tang et al., 2024)",
                confidence=0.92,
            ))
        elif ec <= EC.warn_low:
            chains.append(CausalChain(
                cause=f"Low EC ({ec:.0f} µS/cm) — nutrient solution is too dilute",
                impact="Sub-optimal N uptake impairs chlorophyll synthesis and shoot growth",
                risk="Reduced photosynthetic capacity and lower fruit quality",
                action="Increase fertigation concentration in next irrigation cycle",
                confidence=0.78,
            ))

        if ec >= EC.critical_high:
            chains.append(CausalChain(
                cause=f"Critically high EC ({ec:.0f} µS/cm ≥ {EC.critical_high:.0f} µS/cm)",
                impact="Osmotic imbalance in root zone — water uptake reverses (plasmolysis)",
                risk="Salt toxicity, root burn and rapid decline",
                action="Flush root zone with clean water immediately to dilute salts",
                confidence=0.94,
            ))
        elif ec >= EC.warn_high:
            chains.append(CausalChain(
                cause=f"Elevated EC ({ec:.0f} µS/cm) — salt accumulation building",
                impact="Osmotic stress reduces water availability even at adequate soil moisture",
                risk="Gradual root damage and reduced fruit size",
                action="Schedule a leaching irrigation to reduce salt load",
                confidence=0.76,
            ))

        return chains

    # ──────────────────────────────────────── pH pathway

    @staticmethod
    def _ph_chains(ph: float) -> list[CausalChain]:
        chains: list[CausalChain] = []

        if ph <= PH.critical_low:
            chains.append(CausalChain(
                cause=f"Critically acid soil pH ({ph:.2f} ≤ {PH.critical_low:.1f})",
                impact="Al³⁺ and Mn²⁺ toxic at low pH; Ca, Mg, P precipitation blocks uptake",
                risk="Severe root toxicity and complete nutrient lock-out",
                action="Apply agricultural lime urgently to raise pH to 5.5-6.5",
                confidence=0.95,
            ))
        elif ph <= PH.warn_low:
            chains.append(CausalChain(
                cause=f"Acid soil pH ({ph:.2f} ≤ {PH.warn_low:.1f})",
                impact="Phosphate adsorption increases; Ca and Mg solubility falls",
                risk="P deficiency → poor flowering; Ca deficiency → blossom-end rot",
                action="Apply lime or dolomite; retest pH after 2 weeks",
                confidence=0.80,
            ))
        elif ph < PH.optimal_low:
            chains.append(CausalChain(
                cause=f"pH {ph:.2f} below optimal minimum {PH.optimal_low:.1f}",
                impact="Mild P and Ca availability reduction",
                risk="Subtle growth and quality impact over time",
                action="Schedule lime application at next convenient window",
                confidence=0.65,
            ))

        if ph >= PH.critical_high:
            chains.append(CausalChain(
                cause=f"Critically alkaline pH ({ph:.2f} ≥ {PH.critical_high:.1f})",
                impact="Fe, Zn, Mn precipitate — complete micronutrient lock-out",
                risk="Severe chlorosis and fruit quality collapse",
                action="Apply elemental sulfur or acidic fertiliser urgently",
                confidence=0.95,
            ))
        elif ph >= PH.warn_high:
            chains.append(CausalChain(
                cause=f"Alkaline pH ({ph:.2f} ≥ {PH.warn_high:.1f}) — above optimal 6.5",
                impact="Iron chlorosis onset; zinc and manganese availability falls 50-80 %",
                risk="Leaf yellowing, reduced photosynthesis, poor fruit colouration",
                action="Apply sulfur-based acidifier to return pH to 5.5-6.5",
                confidence=0.80,
            ))
        elif ph > PH.optimal_high:
            chains.append(CausalChain(
                cause=f"pH {ph:.2f} slightly above optimal {PH.optimal_high:.1f}",
                impact="Early micronutrient availability decline",
                risk="Minor yield impact if trend continues upward",
                action="Monitor pH trend; plan acidification if it rises further",
                confidence=0.62,
            ))

        return chains

    # ──────────────────────────────────────── Phytophthora pathway

    @staticmethod
    def _phytophthora_chains(temperature: float, humidity: float) -> list[CausalChain]:
        chains: list[CausalChain] = []
        in_range = PHYTOPHTHORA.temp_favour_low <= temperature <= PHYTOPHTHORA.temp_favour_high

        if in_range and humidity >= PHYTOPHTHORA.moisture_critical:
            chains.append(CausalChain(
                cause=(
                    f"Warm temperature ({temperature:.1f} °C) + critical soil wetness "
                    f"({humidity:.1f} % ≥ {PHYTOPHTHORA.moisture_critical:.0f} %)"
                ),
                impact="P. palmivora sporangia germinate and zoospores swim to roots in saturated soil",
                risk="Root and stem canker infection — can kill mature trees within weeks",
                action=(
                    "Inspect all trees for canker; apply phosphonate fungicide; "
                    "improve drainage urgently; apply mulch to reduce splash"
                ),
                confidence=0.93,
            ))
        elif in_range and humidity >= PHYTOPHTHORA.moisture_warn:
            chains.append(CausalChain(
                cause=(
                    f"Phytophthora-favourable environment: T={temperature:.1f} °C + "
                    f"soil moisture {humidity:.1f} % ≥ {PHYTOPHTHORA.moisture_warn:.0f} %"
                ),
                impact="Low-level P. palmivora sporulation possible in wet micro-sites",
                risk="Disease establishment if wet period continues",
                action="Apply preventive mulch; improve soil drainage; reduce N fertiliser",
                confidence=0.75,
            ))

        return chains

    # ──────────────────────────────────────── VPD pathway

    @staticmethod
    def _vpd_chains(vpd: float, temperature: float, humidity: float) -> list[CausalChain]:
        chains: list[CausalChain] = []

        if vpd >= VPD.critical_high:
            chains.append(CausalChain(
                cause=f"Critical VPD {vpd:.2f} kPa (T={temperature:.1f} °C, H={humidity:.1f} %)",
                impact="Stomata close fully to prevent desiccation — CO₂ fixation stops",
                risk="Water stress even in moist soil; fruit shrinkage and drop",
                action="Activate micro-sprinkler misting to cool canopy and raise local humidity",
                confidence=0.90,
            ))
        elif vpd >= VPD.warn_high:
            chains.append(CausalChain(
                cause=f"Elevated VPD {vpd:.2f} kPa (T={temperature:.1f} °C, H={humidity:.1f} %)",
                impact="Transpiration demand exceeds comfortable root supply rate",
                risk="Stomatal partial closure reduces photosynthesis 20-40 %",
                action="Activate misting; consider extra irrigation cycle to buffer root zone",
                confidence=0.78,
            ))

        return chains

    # ──────────────────────────────────────── trend-based chains

    @staticmethod
    def _trend_chains(trends: list[str], humidity: float, temperature: float) -> list[CausalChain]:
        chains: list[CausalChain] = []

        if "prolonged_dry_period" in trends:
            chains.append(CausalChain(
                cause="Prolonged dry period detected in memory (soil moisture consistently low)",
                impact="Dry-spell stress physiology activates hormonal flowering initiation",
                risk="Flower buds may emerge in 30-50 days if dry spell continues ~15 days",
                action=(
                    "Schedule bud monitoring from week 3; prepare pre-flowering "
                    "fertigation (high K, reduced N)"
                ),
                confidence=0.70,
            ))

        if "rising_temperature" in trends:
            chains.append(CausalChain(
                cause="Sustained temperature increase detected across recent sensor history",
                impact="Rising VPD trend will amplify water demand and accelerate soil drying",
                risk="Compounding heat × drought stress risk if irrigation is not increased",
                action="Increase irrigation frequency proactively; monitor VPD hourly",
                confidence=0.72,
            ))

        if "excessive_wet_period" in trends:
            chains.append(CausalChain(
                cause="Sustained waterlogged period in sensor memory",
                impact="Chronic root oxygen deprivation weakens tree immune response",
                risk="Systemic Phytophthora vulnerability across entire planting",
                action="Audit drainage infrastructure; apply preventive phosphonate",
                confidence=0.80,
            ))

        if "increasing_vpd" in trends:
            chains.append(CausalChain(
                cause="VPD has been rising steadily across sensor history",
                impact="Atmospheric evaporative demand will soon exceed root supply even at 50 % VWC",
                risk="Emerging water stress without visible soil moisture warning",
                action="Increase irrigation frequency before soil moisture drops below optimal",
                confidence=0.68,
            ))

        return chains
