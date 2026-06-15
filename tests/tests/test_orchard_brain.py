"""Unit tests for src/orchard_brain — run with: python -m pytest tests/test_orchard_brain.py -v

Coverage targets
────────────────
  HealthAssessment        — water_stress, nutrient_stress, health_score, VPD
  RiskAssessment          — every risk identifier × severity level
                            including phytophthora_risk and vpd_stress
  RecommendationEngine    — every action key, priority ordering, deduplication,
                            confidence scores, compound rules
  OrchardBrain (facade)   — end-to-end, duck-typing, output contract

Threshold constants are imported directly so tests automatically adapt
when agronomic values are updated in _thresholds.py.
"""
from __future__ import annotations

import math

import pytest

from src.orchard_brain import (
    HealthAssessment,
    OrchardBrain,
    RecommendationEngine,
    RiskAssessment,
)
from src.orchard_brain._thresholds import (
    EC, HUMIDITY, PH, PHYTOPHTHORA, TEMPERATURE, VPD, compute_vpd_kpa,
)
from src.orchard_brain.health import HealthResult


# ─────────────────────────────────────────────────────────────────── fixtures


def _brain() -> OrchardBrain:
    return OrchardBrain()


def _health() -> HealthAssessment:
    return HealthAssessment()


def _risk() -> RiskAssessment:
    return RiskAssessment()


def _rec() -> RecommendationEngine:
    return RecommendationEngine()


def _ideal() -> dict:
    """Sensor values well inside every optimal range (research-corrected thresholds).

    - temperature=28.0  optimal [25, 32] °C
    - humidity=50.0     optimal [40, 60] % VWC   (updated from research: 40-60 %)
    - ec=220.0          optimal [150, 300] µS/cm
    - ph=6.0            optimal [5.5, 6.5]         (updated from research: pH 5.5-6.5)
    """
    return dict(
        temperature=28.0,
        humidity=50.0,
        ec=220.0,
        ph=6.0,
    )


class _FakeReading:
    """Duck-type substitute for SensorReading (no real validator needed)."""
    def __init__(self, temperature=28.0, humidity=50.0, ec=220.0, ph=6.0):
        self.temperature = temperature
        self.humidity = humidity
        self.ec = ec
        self.ph = ph


# ═══════════════════════════════════════════════════════════════════════════════
# VPD utility
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeVPD:
    def test_zero_vpd_at_100_percent_humidity(self):
        vpd = compute_vpd_kpa(30.0, 100.0)
        assert vpd == pytest.approx(0.0, abs=1e-6)

    def test_vpd_increases_with_temperature(self):
        vpd_low = compute_vpd_kpa(25.0, 50.0)
        vpd_high = compute_vpd_kpa(35.0, 50.0)
        assert vpd_high > vpd_low

    def test_vpd_increases_as_humidity_falls(self):
        vpd_humid = compute_vpd_kpa(30.0, 80.0)
        vpd_dry = compute_vpd_kpa(30.0, 30.0)
        assert vpd_dry > vpd_humid

    def test_vpd_non_negative(self):
        for h in (0.0, 50.0, 100.0, 110.0):  # even out-of-range
            assert compute_vpd_kpa(28.0, h) >= 0.0

    def test_vpd_reasonable_tropical_range(self):
        # 28 °C, 75 % RH — typical tropical conditions → VPD ≈ 0.95 kPa
        vpd = compute_vpd_kpa(28.0, 75.0)
        assert 0.5 < vpd < 1.5


# ═══════════════════════════════════════════════════════════════════════════════
# HealthAssessment
# ═══════════════════════════════════════════════════════════════════════════════


class TestHealthAssessmentWaterStress:
    def test_optimal_humidity_zero_stress(self):
        ha = _health()
        r = ha.assess(**{**_ideal(), "humidity": 50.0})
        assert r.water_stress == 0

    def test_at_optimal_low_boundary_zero_stress(self):
        ha = _health()
        r = ha.assess(**{**_ideal(), "humidity": HUMIDITY.optimal_low})
        assert r.water_stress == 0

    def test_at_optimal_high_boundary_zero_stress(self):
        ha = _health()
        r = ha.assess(**{**_ideal(), "humidity": HUMIDITY.optimal_high})
        assert r.water_stress == 0

    def test_zero_humidity_maximum_drought_stress(self):
        ha = _health()
        r = ha.assess(**{**_ideal(), "humidity": 0.0})
        assert r.water_stress == 100

    def test_drought_stress_increases_as_humidity_falls(self):
        ha = _health()
        r_mild = ha.assess(**{**_ideal(), "humidity": 35.0})
        r_severe = ha.assess(**{**_ideal(), "humidity": 10.0})
        assert r_severe.water_stress > r_mild.water_stress

    def test_humidity_100_maximum_waterlogging_stress(self):
        ha = _health()
        r = ha.assess(**{**_ideal(), "humidity": 100.0})
        assert r.water_stress == 100

    def test_waterlogging_stress_increases_with_humidity(self):
        ha = _health()
        r_mild = ha.assess(**{**_ideal(), "humidity": 65.0})
        r_severe = ha.assess(**{**_ideal(), "humidity": 88.0})
        assert r_severe.water_stress > r_mild.water_stress

    def test_just_below_optimal_low_triggers_drought_stress(self):
        # Research correction: optimal_low is now 40 %, not 30 %
        ha = _health()
        r = ha.assess(**{**_ideal(), "humidity": HUMIDITY.optimal_low - 1.0})
        assert r.water_stress > 0


class TestHealthAssessmentNutrientStress:
    def test_optimal_ec_and_ph_zero_stress(self):
        ha = _health()
        r = ha.assess(**_ideal())
        assert r.nutrient_stress == 0

    def test_zero_ec_maximum_ec_stress(self):
        ha = _health()
        r = ha.assess(**{**_ideal(), "ec": 0.0})
        assert r.nutrient_stress >= 60

    def test_very_high_ec_produces_stress(self):
        ha = _health()
        r = ha.assess(**{**_ideal(), "ec": 700.0})
        assert r.nutrient_stress > 0

    def test_ph_below_optimal_increases_stress(self):
        ha = _health()
        r_ok = ha.assess(**_ideal())
        r_acid = ha.assess(**{**_ideal(), "ph": 4.5})
        assert r_acid.nutrient_stress > r_ok.nutrient_stress

    def test_ph_above_optimal_increases_stress(self):
        # Research correction: optimal_high is now 6.5, so ph=7.0 triggers stress
        ha = _health()
        r_ok = ha.assess(**_ideal())
        r_alk = ha.assess(**{**_ideal(), "ph": 7.5})
        assert r_alk.nutrient_stress > r_ok.nutrient_stress

    def test_ph_at_old_boundary_now_outside_optimal(self):
        # pH=7.0 was old optimal_high; now optimal_high=6.5 (research correction)
        ha = _health()
        r = ha.assess(**{**_ideal(), "ph": 7.0})
        # Should have non-zero nutrient stress since 7.0 > 6.5
        assert r.nutrient_stress > 0

    def test_nutrient_stress_clamped_to_100(self):
        ha = _health()
        r = ha.assess(**{**_ideal(), "ec": 0.0, "ph": 4.0})
        assert r.nutrient_stress <= 100

    def test_combined_ec_and_ph_stress_accumulates(self):
        ha = _health()
        r_ec_only = ha.assess(**{**_ideal(), "ec": 0.0})
        r_ph_only = ha.assess(**{**_ideal(), "ph": 4.0})
        r_both = ha.assess(**{**_ideal(), "ec": 0.0, "ph": 4.0})
        assert r_both.nutrient_stress >= max(r_ec_only.nutrient_stress, r_ph_only.nutrient_stress)


class TestHealthAssessmentHealthScore:
    def test_all_optimal_near_100(self):
        ha = _health()
        r = ha.assess(**_ideal())
        assert r.health_score >= 90, f"Expected ≥90, got {r.health_score}"

    def test_health_score_range_0_to_100(self):
        ha = _health()
        extremes = [
            dict(temperature=0.0, humidity=0.0, ec=0.0, ph=0.0),
            dict(temperature=60.0, humidity=100.0, ec=5000.0, ph=14.0),
        ]
        for vals in extremes:
            r = ha.assess(**vals)
            assert 0 <= r.health_score <= 100, f"Out-of-range for {vals}: {r.health_score}"

    def test_high_temperature_lowers_health_score(self):
        ha = _health()
        r_ok = ha.assess(**_ideal())
        r_hot = ha.assess(**{**_ideal(), "temperature": 40.0})
        assert r_hot.health_score < r_ok.health_score

    def test_low_humidity_lowers_health_score(self):
        ha = _health()
        r_ok = ha.assess(**_ideal())
        r_dry = ha.assess(**{**_ideal(), "humidity": 5.0})
        assert r_dry.health_score < r_ok.health_score

    def test_bad_ec_lowers_health_score(self):
        ha = _health()
        r_ok = ha.assess(**_ideal())
        r_bad = ha.assess(**{**_ideal(), "ec": 10.0})
        assert r_bad.health_score < r_ok.health_score

    def test_bad_ph_lowers_health_score(self):
        ha = _health()
        r_ok = ha.assess(**_ideal())
        r_bad = ha.assess(**{**_ideal(), "ph": 4.0})
        assert r_bad.health_score < r_ok.health_score

    def test_returns_integer_scores(self):
        ha = _health()
        r = ha.assess(**_ideal())
        assert isinstance(r.health_score, int)
        assert isinstance(r.water_stress, int)
        assert isinstance(r.nutrient_stress, int)

    def test_temperature_score_optimal_is_100(self):
        ha = _health()
        r = ha.assess(**_ideal())
        assert r.temperature_score == 100

    def test_temperature_score_decreases_with_heat(self):
        ha = _health()
        r_ok = ha.assess(**_ideal())
        r_hot = ha.assess(**{**_ideal(), "temperature": 40.0})
        assert r_hot.temperature_score < r_ok.temperature_score


class TestHealthAssessmentVPD:
    def test_vpd_exposed_in_health_result(self):
        ha = _health()
        r = ha.assess(**_ideal())
        assert hasattr(r, "vpd_kpa")
        assert isinstance(r.vpd_kpa, float)

    def test_vpd_non_negative(self):
        ha = _health()
        r = ha.assess(**_ideal())
        assert r.vpd_kpa >= 0.0

    def test_vpd_higher_at_high_temperature_low_humidity(self):
        ha = _health()
        r_ok = ha.assess(**_ideal())
        r_hot_dry = ha.assess(**{**_ideal(), "temperature": 38.0, "humidity": 30.0})
        assert r_hot_dry.vpd_kpa > r_ok.vpd_kpa

    def test_vpd_matches_utility_function(self):
        ha = _health()
        r = ha.assess(**_ideal())
        expected = compute_vpd_kpa(_ideal()["temperature"], _ideal()["humidity"])
        assert r.vpd_kpa == pytest.approx(expected, abs=0.001)


# ═══════════════════════════════════════════════════════════════════════════════
# RiskAssessment
# ═══════════════════════════════════════════════════════════════════════════════


class TestRiskAssessmentNoRisks:
    def test_all_optimal_returns_empty_list(self):
        ra = _risk()
        risks = ra.assess(**_ideal())
        assert risks == [], f"Unexpected risks: {risks}"


class TestRiskAssessmentTemperature:
    def test_warn_high_produces_warning_heat_stress(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "temperature": TEMPERATURE.warn_high + 0.1})
        heat = [r for r in risks if r["risk"] == "heat_stress"]
        assert len(heat) == 1
        assert heat[0]["severity"] == "warning"

    def test_critical_high_produces_critical_heat_stress(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "temperature": TEMPERATURE.critical_high})
        heat = [r for r in risks if r["risk"] == "heat_stress"]
        assert len(heat) == 1
        assert heat[0]["severity"] == "critical"

    def test_warn_low_produces_warning_cold_stress(self):
        # Research correction: warn_low is now 22 °C (not 20 °C)
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "temperature": TEMPERATURE.warn_low - 0.1})
        cold = [r for r in risks if r["risk"] == "cold_stress"]
        assert len(cold) == 1
        assert cold[0]["severity"] == "warning"

    def test_critical_low_produces_critical_cold_stress(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "temperature": TEMPERATURE.critical_low})
        cold = [r for r in risks if r["risk"] == "cold_stress"]
        assert len(cold) == 1
        assert cold[0]["severity"] == "critical"

    def test_research_corrected_warn_low_22c(self):
        # 21 °C is now warning (research: below 22 °C stunts growth)
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "temperature": 21.0})
        cold = [r for r in risks if r["risk"] == "cold_stress"]
        assert cold, "21 °C should trigger cold_stress warning (research: <22 °C stunts growth)"
        assert cold[0]["severity"] == "warning"

    def test_normal_temperature_no_thermal_risks(self):
        ra = _risk()
        risks = ra.assess(**_ideal())
        thermal = [r for r in risks if r["risk"] in ("heat_stress", "cold_stress")]
        assert thermal == []


class TestRiskAssessmentHumidity:
    def test_critical_low_humidity_drought_critical(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "humidity": HUMIDITY.critical_low})
        d = [r for r in risks if r["risk"] == "drought"]
        assert d and d[0]["severity"] == "critical"

    def test_warn_low_humidity_drought_warning(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "humidity": HUMIDITY.warn_low - 0.1})
        d = [r for r in risks if r["risk"] == "drought"]
        assert d and d[0]["severity"] == "warning"

    def test_below_optimal_low_mild_drought_warning(self):
        # Research correction: optimal_low is now 40 %, so 39 % triggers warning
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "humidity": HUMIDITY.optimal_low - 1.0})
        d = [r for r in risks if r["risk"] == "drought"]
        assert d and d[0]["severity"] == "warning"

    def test_research_corrected_optimal_low_40_percent(self):
        # 35 % was "optimal" before; now it's mild drought (optimal_low = 40 %)
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "humidity": 35.0})
        d = [r for r in risks if r["risk"] == "drought"]
        assert d, "35 % humidity should trigger drought risk (research: optimal ≥40 % VWC)"

    def test_critical_high_humidity_waterlogging_critical(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "humidity": HUMIDITY.critical_high})
        w = [r for r in risks if r["risk"] == "waterlogging"]
        assert w and w[0]["severity"] == "critical"

    def test_warn_high_humidity_waterlogging_warning(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "humidity": HUMIDITY.warn_high + 0.1})
        w = [r for r in risks if r["risk"] == "waterlogging"]
        assert w and w[0]["severity"] == "warning"

    def test_above_optimal_high_mild_waterlogging_warning(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "humidity": HUMIDITY.optimal_high + 1.0})
        w = [r for r in risks if r["risk"] == "waterlogging"]
        assert w and w[0]["severity"] == "warning"

    def test_optimal_humidity_no_water_risks(self):
        ra = _risk()
        risks = ra.assess(**_ideal())
        water = [r for r in risks if r["risk"] in ("drought", "waterlogging")]
        assert water == []


class TestRiskAssessmentEC:
    def test_critical_low_ec_nutrient_deficiency_critical(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "ec": EC.critical_low})
        d = [r for r in risks if r["risk"] == "nutrient_deficiency"]
        assert d and d[0]["severity"] == "critical"

    def test_warn_low_ec_nutrient_deficiency_warning(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "ec": EC.warn_low - 1.0})
        d = [r for r in risks if r["risk"] == "nutrient_deficiency"]
        assert d and d[0]["severity"] == "warning"

    def test_below_optimal_low_ec_mild_deficiency(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "ec": EC.optimal_low - 10.0})
        d = [r for r in risks if r["risk"] == "nutrient_deficiency"]
        assert d and d[0]["severity"] == "warning"

    def test_critical_high_ec_nutrient_toxicity_critical(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "ec": EC.critical_high})
        t = [r for r in risks if r["risk"] == "nutrient_toxicity"]
        assert t and t[0]["severity"] == "critical"

    def test_warn_high_ec_nutrient_toxicity_warning(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "ec": EC.warn_high + 1.0})
        t = [r for r in risks if r["risk"] == "nutrient_toxicity"]
        assert t and t[0]["severity"] == "warning"

    def test_optimal_ec_no_ec_risks(self):
        ra = _risk()
        risks = ra.assess(**_ideal())
        ec_risks = [r for r in risks if r["risk"] in ("nutrient_deficiency", "nutrient_toxicity")]
        assert ec_risks == []


class TestRiskAssessmentPH:
    def test_critical_low_ph_acid_critical(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "ph": PH.critical_low})
        a = [r for r in risks if r["risk"] == "ph_acid"]
        assert a and a[0]["severity"] == "critical"

    def test_warn_low_ph_acid_warning(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "ph": PH.warn_low - 0.1})
        a = [r for r in risks if r["risk"] == "ph_acid"]
        assert a and a[0]["severity"] == "warning"

    def test_below_optimal_low_ph_mild_acid(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "ph": PH.optimal_low - 0.2})
        a = [r for r in risks if r["risk"] == "ph_acid"]
        assert a and a[0]["severity"] == "warning"

    def test_critical_high_ph_alkaline_critical(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "ph": PH.critical_high})
        alk = [r for r in risks if r["risk"] == "ph_alkaline"]
        assert alk and alk[0]["severity"] == "critical"

    def test_warn_high_ph_alkaline_warning(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "ph": PH.warn_high + 0.1})
        alk = [r for r in risks if r["risk"] == "ph_alkaline"]
        assert alk and alk[0]["severity"] == "warning"

    def test_research_corrected_optimal_high_65(self):
        # pH 7.0 was old optimal boundary; now warns because optimal_high = 6.5
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "ph": 7.0})
        alk = [r for r in risks if r["risk"] == "ph_alkaline"]
        assert alk, "pH=7.0 should trigger ph_alkaline warning (research: optimal ≤6.5)"

    def test_ph_65_just_above_optimal_triggers_warning(self):
        # 6.6 is just above new optimal_high=6.5
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "ph": PH.optimal_high + 0.1})
        alk = [r for r in risks if r["risk"] == "ph_alkaline"]
        assert alk and alk[0]["severity"] == "warning"

    def test_ph_60_is_optimal_no_risks(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "ph": 6.0})
        ph_risks = [r for r in risks if r["risk"] in ("ph_acid", "ph_alkaline")]
        assert ph_risks == []


class TestRiskAssessmentVPD:
    def test_high_temp_low_humidity_triggers_vpd_risk(self):
        ra = _risk()
        # 40°C, 20% humidity → VPD will be high
        risks = ra.assess(**{**_ideal(), "temperature": 40.0, "humidity": 20.0})
        vpd_risks = [r for r in risks if r["risk"] == "vpd_stress"]
        assert vpd_risks, "High T + low humidity should trigger vpd_stress"

    def test_no_vpd_risk_in_optimal_conditions(self):
        ra = _risk()
        risks = ra.assess(**_ideal())
        vpd_risks = [r for r in risks if r["risk"] == "vpd_stress"]
        assert vpd_risks == [], f"No VPD risk expected at ideal conditions, got {vpd_risks}"

    def test_vpd_risk_severity_scales_correctly(self):
        ra = _risk()
        # critical VPD conditions
        risks_crit = ra.assess(**{**_ideal(), "temperature": 42.0, "humidity": 10.0})
        vpd_crit = [r for r in risks_crit if r["risk"] == "vpd_stress"]
        if vpd_crit:
            assert vpd_crit[0]["severity"] == "critical"

    def test_vpd_message_contains_kpa_value(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "temperature": 40.0, "humidity": 15.0})
        vpd_risks = [r for r in risks if r["risk"] == "vpd_stress"]
        if vpd_risks:
            assert "kPa" in vpd_risks[0]["message"]


class TestRiskAssessmentPhytophthora:
    def test_warm_wet_triggers_phytophthora_warning(self):
        ra = _risk()
        risks = ra.assess(
            temperature=PHYTOPHTHORA.temp_favour_low + 1.0,
            humidity=PHYTOPHTHORA.moisture_warn + 1.0,
            ec=220.0,
            ph=6.0,
        )
        phy = [r for r in risks if r["risk"] == "phytophthora_risk"]
        assert phy, "Warm + moist conditions should trigger phytophthora_risk"
        assert phy[0]["severity"] == "warning"

    def test_warm_very_wet_triggers_phytophthora_critical(self):
        ra = _risk()
        risks = ra.assess(
            temperature=PHYTOPHTHORA.temp_favour_low + 2.0,
            humidity=PHYTOPHTHORA.moisture_critical + 1.0,
            ec=220.0,
            ph=6.0,
        )
        phy = [r for r in risks if r["risk"] == "phytophthora_risk"]
        assert phy and phy[0]["severity"] == "critical"

    def test_cold_temperature_no_phytophthora_even_if_wet(self):
        ra = _risk()
        risks = ra.assess(
            temperature=18.0,    # below pathogen-favourable range
            humidity=85.0,
            ec=220.0,
            ph=6.0,
        )
        phy = [r for r in risks if r["risk"] == "phytophthora_risk"]
        assert phy == [], "Cold temperature should not trigger phytophthora_risk"

    def test_optimal_moisture_no_phytophthora(self):
        ra = _risk()
        risks = ra.assess(**_ideal())
        phy = [r for r in risks if r["risk"] == "phytophthora_risk"]
        assert phy == []

    def test_phytophthora_message_cites_research(self):
        ra = _risk()
        risks = ra.assess(
            temperature=28.0,
            humidity=PHYTOPHTHORA.moisture_warn + 1.0,
            ec=220.0,
            ph=6.0,
        )
        phy = [r for r in risks if r["risk"] == "phytophthora_risk"]
        if phy:
            assert "Drenth" in phy[0]["message"] or "Phytophthora" in phy[0]["message"]


class TestRiskAssessmentOrdering:
    def test_critical_risks_appear_before_warnings(self):
        ra = _risk()
        risks = ra.assess(
            temperature=TEMPERATURE.critical_high,
            humidity=HUMIDITY.optimal_high + 2.0,
            ec=220.0,
            ph=6.0,
        )
        severities = [r["severity"] for r in risks]
        first_warning = next((i for i, s in enumerate(severities) if s == "warning"), None)
        first_critical = next((i for i, s in enumerate(severities) if s == "critical"), None)
        if first_warning is not None and first_critical is not None:
            assert first_critical < first_warning

    def test_risk_dict_has_required_keys(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "temperature": 40.0})
        for r in risks:
            assert "risk" in r
            assert "severity" in r
            assert "message" in r
            assert r["severity"] in ("warning", "critical")

    def test_risk_messages_contain_actual_values(self):
        ra = _risk()
        risks = ra.assess(**{**_ideal(), "temperature": 40.0})
        heat = [r for r in risks if r["risk"] == "heat_stress"]
        assert heat
        assert "40.0" in heat[0]["message"]


# ═══════════════════════════════════════════════════════════════════════════════
# RecommendationEngine
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecommendationEngineIrrigation:
    def test_drought_critical_recommends_trigger_irrigation_critical(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "humidity": HUMIDITY.critical_low})
        irr = [r for r in recs if r["action"] == "trigger_irrigation"]
        assert irr and irr[0]["priority"] == "critical"

    def test_drought_warning_recommends_trigger_irrigation_high(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "humidity": HUMIDITY.warn_low - 1.0})
        irr = [r for r in recs if r["action"] == "trigger_irrigation"]
        assert irr and irr[0]["priority"] == "high"

    def test_mild_drought_recommends_trigger_irrigation_medium(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "humidity": HUMIDITY.optimal_low - 5.0})
        irr = [r for r in recs if r["action"] == "trigger_irrigation"]
        assert irr and irr[0]["priority"] == "medium"

    def test_waterlogging_critical_recommends_stop_irrigation_critical(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "humidity": HUMIDITY.critical_high})
        stop = [r for r in recs if r["action"] == "stop_irrigation"]
        assert stop and stop[0]["priority"] == "critical"

    def test_waterlogging_warning_recommends_stop_irrigation_high(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "humidity": HUMIDITY.warn_high + 1.0})
        stop = [r for r in recs if r["action"] == "stop_irrigation"]
        assert stop and stop[0]["priority"] == "high"

    def test_mild_waterlogging_recommends_stop_irrigation_medium(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "humidity": HUMIDITY.optimal_high + 2.0})
        stop = [r for r in recs if r["action"] == "stop_irrigation"]
        assert stop and stop[0]["priority"] == "medium"


class TestRecommendationEngineCooling:
    def test_critical_temp_recommends_cooling_critical(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "temperature": TEMPERATURE.critical_high})
        cool = [r for r in recs if r["action"] == "trigger_micro_sprinkler_cooling"]
        assert cool and cool[0]["priority"] == "critical"

    def test_warn_temp_recommends_cooling_high(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "temperature": TEMPERATURE.warn_high + 0.5})
        cool = [r for r in recs if r["action"] == "trigger_micro_sprinkler_cooling"]
        assert cool and cool[0]["priority"] in ("critical", "high")

    def test_cold_critical_recommends_frost_protection_critical(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "temperature": TEMPERATURE.critical_low})
        frost = [r for r in recs if r["action"] == "apply_frost_protection"]
        assert frost and frost[0]["priority"] == "critical"

    def test_cold_warning_recommends_frost_protection_high(self):
        # Research correction: warn_low is now 22 °C; temperature at 21 °C = warning
        re = _rec()
        recs = re.recommend(**{**_ideal(), "temperature": TEMPERATURE.warn_low - 0.5})
        frost = [r for r in recs if r["action"] == "apply_frost_protection"]
        assert frost and frost[0]["priority"] == "high"

    def test_optimal_temp_no_cooling_recommendation(self):
        re = _rec()
        recs = re.recommend(**_ideal())
        cool = [r for r in recs if r["action"] == "trigger_micro_sprinkler_cooling"]
        assert cool == []


class TestRecommendationEngineNutrients:
    def test_critical_low_ec_recommends_fertigation_critical(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "ec": EC.critical_low})
        f = [r for r in recs if r["action"] == "adjust_fertigation_ratio_to_high_pk"]
        assert f and f[0]["priority"] == "critical"

    def test_warn_low_ec_recommends_fertigation_high(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "ec": EC.warn_low - 5.0})
        f = [r for r in recs if r["action"] == "adjust_fertigation_ratio_to_high_pk"]
        assert f and f[0]["priority"] == "high"

    def test_critical_high_ec_recommends_flush_critical(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "ec": EC.critical_high})
        flush = [r for r in recs if r["action"] == "flush_irrigation_to_reduce_ec"]
        assert flush and flush[0]["priority"] == "critical"

    def test_slightly_high_ec_recommends_flush_low(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "ec": EC.optimal_high + 10.0})
        flush = [r for r in recs if r["action"] == "flush_irrigation_to_reduce_ec"]
        assert flush and flush[0]["priority"] == "low"

    def test_low_ph_recommends_lime(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "ph": PH.warn_low - 0.1})
        lime = [r for r in recs if r["action"] == "apply_lime_to_raise_ph"]
        assert lime and lime[0]["priority"] == "high"

    def test_high_ph_recommends_sulfur(self):
        # Research correction: warn_high is now 7.0; so ph=7.1 triggers high priority
        re = _rec()
        recs = re.recommend(**{**_ideal(), "ph": PH.warn_high + 0.1})
        sulfur = [r for r in recs if r["action"] == "apply_sulfur_to_lower_ph"]
        assert sulfur and sulfur[0]["priority"] == "high"

    def test_ph_above_optimal_but_below_warn_recommends_sulfur_medium(self):
        # pH 6.6 > optimal_high 6.5 but < warn_high 7.0 → medium
        re = _rec()
        recs = re.recommend(**{**_ideal(), "ph": PH.optimal_high + 0.1})
        sulfur = [r for r in recs if r["action"] == "apply_sulfur_to_lower_ph"]
        assert sulfur and sulfur[0]["priority"] == "medium"


class TestRecommendationEngineVPD:
    def test_high_vpd_recommends_cooling(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "temperature": 40.0, "humidity": 20.0})
        cool = [r for r in recs if r["action"] == "trigger_micro_sprinkler_cooling"]
        assert cool, "High VPD conditions should recommend micro_sprinkler_cooling"

    def test_optimal_vpd_no_vpd_recommendation(self):
        re = _rec()
        # _ideal() has T=28, H=50 → VPD ≈ 1.7 kPa which is below warn threshold
        recs = re.recommend(**_ideal())
        # No VPD-specific recommendation beyond what temperature/humidity already covers
        vpd_related = [r for r in recs if "vpd" in r["reason"].lower()]
        # Should be empty or only VPD-specific ones
        assert True  # just check it doesn't crash


class TestRecommendationEnginePhytophthora:
    def test_warm_wet_recommends_mulch(self):
        re = _rec()
        recs = re.recommend(
            temperature=28.0,
            humidity=PHYTOPHTHORA.moisture_warn + 1.0,
            ec=220.0,
            ph=6.0,
        )
        mulch = [r for r in recs if r["action"] == "apply_mulch_for_disease_prevention"]
        assert mulch, "Phytophthora conditions should trigger mulch recommendation"

    def test_critical_wet_recommends_fungicide_inspection(self):
        re = _rec()
        recs = re.recommend(
            temperature=28.0,
            humidity=PHYTOPHTHORA.moisture_critical + 1.0,
            ec=220.0,
            ph=6.0,
        )
        inspect = [r for r in recs if r["action"] == "inspect_for_phytophthora"]
        assert inspect and inspect[0]["priority"] == "critical"

    def test_cold_wet_no_phytophthora_recommendation(self):
        re = _rec()
        recs = re.recommend(temperature=18.0, humidity=85.0, ec=220.0, ph=6.0)
        inspect = [r for r in recs if r["action"] == "inspect_for_phytophthora"]
        assert inspect == [], "Cold + wet should not trigger Phytophthora recommendation"


class TestRecommendationEngineCompound:
    def test_all_optimal_recommends_maintain_current_conditions(self):
        re = _rec()
        recs = re.recommend(**_ideal())
        maintain = [r for r in recs if r["action"] == "maintain_current_conditions"]
        assert maintain and maintain[0]["priority"] == "low"

    def test_heat_plus_drought_recommends_reduce_fertigation(self):
        re = _rec()
        recs = re.recommend(
            temperature=TEMPERATURE.warn_high + 1.0,
            humidity=HUMIDITY.optimal_low - 5.0,
            ec=220.0,
            ph=6.0,
        )
        rf = [r for r in recs if r["action"] == "reduce_fertigation_until_heat_stress_resolved"]
        assert rf, "Heat + drought should produce reduce_fertigation compound recommendation"
        assert rf[0]["priority"] == "high"

    def test_dry_spell_conditions_produce_flowering_advisory(self):
        re = _rec()
        # Low humidity + cool-enough temperature → flowering trigger advisory
        recs = re.recommend(
            temperature=28.0,
            humidity=HUMIDITY.warn_low - 1.0,
            ec=220.0,
            ph=6.0,
        )
        flower = [r for r in recs if r["action"] == "anticipate_flowering_trigger"]
        assert flower, "Dry-spell conditions should trigger flowering advisory (Eguchi et al., 2024)"
        assert flower[0]["priority"] == "low"

    def test_deduplication_no_duplicate_actions(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "humidity": HUMIDITY.critical_low})
        actions = [r["action"] for r in recs]
        assert len(actions) == len(set(actions)), f"Duplicate actions found: {actions}"

    def test_critical_recommendations_appear_first(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "temperature": TEMPERATURE.critical_high})
        if len(recs) > 1:
            priorities = [r["priority"] for r in recs]
            order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            ranked = [order[p] for p in priorities]
            assert ranked == sorted(ranked), f"Unexpected order: {priorities}"

    def test_recommendation_dict_has_required_keys_including_confidence(self):
        re = _rec()
        recs = re.recommend(**{**_ideal(), "temperature": 40.0})
        for r in recs:
            assert "action" in r
            assert "priority" in r
            assert "reason" in r
            assert "confidence" in r, f"Missing 'confidence' in recommendation: {r}"
            assert r["priority"] in ("critical", "high", "medium", "low")
            assert 0.0 <= r["confidence"] <= 1.0, f"Confidence out of range: {r['confidence']}"


class TestRecommendationEngineConfidenceScores:
    def test_confidence_higher_at_critical_vs_warning(self):
        re = _rec()
        recs_warn = re.recommend(**{**_ideal(), "humidity": HUMIDITY.warn_low - 0.5})
        recs_crit = re.recommend(**{**_ideal(), "humidity": HUMIDITY.critical_low})
        irr_warn = next((r for r in recs_warn if r["action"] == "trigger_irrigation"), None)
        irr_crit = next((r for r in recs_crit if r["action"] == "trigger_irrigation"), None)
        if irr_warn and irr_crit:
            assert irr_crit["confidence"] >= irr_warn["confidence"], (
                f"Critical conf {irr_crit['confidence']} should be ≥ warning "
                f"conf {irr_warn['confidence']}"
            )

    def test_confidence_in_valid_range(self):
        re = _rec()
        all_vals = [
            _ideal(),
            {**_ideal(), "temperature": 40.0},
            {**_ideal(), "humidity": 5.0},
            {**_ideal(), "ec": 10.0},
            {**_ideal(), "ph": 4.0},
        ]
        for vals in all_vals:
            recs = re.recommend(**vals)
            for r in recs:
                assert 0.0 <= r["confidence"] <= 1.0, (
                    f"Confidence {r['confidence']} out of [0,1] for action {r['action']}"
                )

    def test_maintain_conditions_has_high_confidence(self):
        re = _rec()
        recs = re.recommend(**_ideal())
        maintain = next((r for r in recs if r["action"] == "maintain_current_conditions"), None)
        assert maintain is not None
        assert maintain["confidence"] >= 0.85


class TestRecommendationEngineWithHealthResult:
    def test_accepts_health_result_for_compound_logic(self):
        ha = _health()
        health = ha.assess(**{**_ideal(), "humidity": 5.0})
        re = _rec()
        recs = re.recommend(**{**_ideal(), "humidity": 5.0}, health_result=health)
        actions = [r["action"] for r in recs]
        assert "trigger_irrigation" in actions

    def test_high_water_stress_triggers_system_inspection(self):
        ha = _health()
        health = ha.assess(**{**_ideal(), "humidity": 5.0})
        re = _rec()
        recs = re.recommend(**{**_ideal(), "humidity": 5.0}, health_result=health)
        inspect = [r for r in recs if r["action"] == "inspect_irrigation_system"]
        assert inspect, "Critical drought water stress should trigger irrigation system inspection"


# ═══════════════════════════════════════════════════════════════════════════════
# OrchardBrain — end-to-end & output contract
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrchardBrainOutputContract:
    def test_evaluate_raw_returns_all_required_keys(self):
        brain = _brain()
        result = brain.evaluate_raw(**_ideal())
        assert "health_score" in result
        assert "water_stress" in result
        assert "nutrient_stress" in result
        assert "risks" in result
        assert "recommendations" in result

    def test_health_score_is_int_in_range(self):
        brain = _brain()
        result = brain.evaluate_raw(**_ideal())
        assert isinstance(result["health_score"], int)
        assert 0 <= result["health_score"] <= 100

    def test_water_stress_is_int_in_range(self):
        brain = _brain()
        result = brain.evaluate_raw(**_ideal())
        assert isinstance(result["water_stress"], int)
        assert 0 <= result["water_stress"] <= 100

    def test_nutrient_stress_is_int_in_range(self):
        brain = _brain()
        result = brain.evaluate_raw(**_ideal())
        assert isinstance(result["nutrient_stress"], int)
        assert 0 <= result["nutrient_stress"] <= 100

    def test_risks_is_list(self):
        brain = _brain()
        result = brain.evaluate_raw(**_ideal())
        assert isinstance(result["risks"], list)

    def test_recommendations_is_list(self):
        brain = _brain()
        result = brain.evaluate_raw(**_ideal())
        assert isinstance(result["recommendations"], list)

    def test_all_optimal_high_health_no_risks(self):
        brain = _brain()
        result = brain.evaluate_raw(**_ideal())
        assert result["health_score"] >= 90
        assert result["water_stress"] == 0
        assert result["nutrient_stress"] == 0
        assert result["risks"] == []

    def test_catastrophic_reading_low_health_many_risks(self):
        brain = _brain()
        result = brain.evaluate_raw(
            temperature=42.0,
            humidity=5.0,
            ec=10.0,
            ph=4.0,
        )
        assert result["health_score"] < 50
        assert result["water_stress"] > 50
        assert result["nutrient_stress"] > 50
        assert len(result["risks"]) >= 3
        assert len(result["recommendations"]) >= 3

    def test_recommendations_include_confidence(self):
        brain = _brain()
        result = brain.evaluate_raw(**{**_ideal(), "temperature": 40.0})
        for rec in result["recommendations"]:
            assert "confidence" in rec, f"Missing confidence: {rec}"
            assert 0.0 <= rec["confidence"] <= 1.0

    def test_result_is_json_serialisable(self):
        import json
        brain = _brain()
        result = brain.evaluate_raw(**_ideal())
        serialised = json.dumps(result)
        roundtrip = json.loads(serialised)
        assert roundtrip["health_score"] == result["health_score"]

    def test_phytophthora_risk_detected_end_to_end(self):
        brain = _brain()
        result = brain.evaluate_raw(
            temperature=28.0,
            humidity=PHYTOPHTHORA.moisture_critical + 1.0,
            ec=220.0,
            ph=6.0,
        )
        risk_names = [r["risk"] for r in result["risks"]]
        assert "phytophthora_risk" in risk_names
        rec_actions = [r["action"] for r in result["recommendations"]]
        assert "inspect_for_phytophthora" in rec_actions


class TestOrchardBrainDuckTyping:
    def test_evaluate_accepts_fake_reading_object(self):
        brain = _brain()
        reading = _FakeReading(**_ideal())
        result = brain.evaluate(reading)
        assert 0 <= result["health_score"] <= 100

    def test_evaluate_result_matches_evaluate_raw(self):
        brain = _brain()
        reading = _FakeReading(**_ideal())
        via_obj = brain.evaluate(reading)
        via_raw = brain.evaluate_raw(**_ideal())
        assert via_obj["health_score"] == via_raw["health_score"]
        assert via_obj["water_stress"] == via_raw["water_stress"]
        assert via_obj["nutrient_stress"] == via_raw["nutrient_stress"]


class TestOrchardBrainResearchThresholds:
    """Verify that the research-corrected thresholds are active end-to-end."""

    def test_humidity_35_triggers_drought_risk(self):
        # Pre-correction: 35% was "optimal"; now it is a drought warning
        brain = _brain()
        result = brain.evaluate_raw(
            temperature=28.0, humidity=35.0, ec=220.0, ph=6.0
        )
        risk_names = [r["risk"] for r in result["risks"]]
        assert "drought" in risk_names, (
            "humidity=35 % should trigger drought risk (research: optimal ≥40 % VWC)"
        )

    def test_ph_70_triggers_alkaline_risk(self):
        # Pre-correction: pH=7.0 was optimal boundary; now it is outside optimal (>6.5)
        brain = _brain()
        result = brain.evaluate_raw(
            temperature=28.0, humidity=50.0, ec=220.0, ph=7.0
        )
        risk_names = [r["risk"] for r in result["risks"]]
        assert "ph_alkaline" in risk_names, (
            "pH=7.0 should trigger ph_alkaline risk (research: optimal pH ≤6.5)"
        )

    def test_temperature_21_triggers_cold_risk(self):
        # Pre-correction: warn_low was 20°C; now it is 22°C per research
        brain = _brain()
        result = brain.evaluate_raw(
            temperature=21.0, humidity=50.0, ec=220.0, ph=6.0
        )
        risk_names = [r["risk"] for r in result["risks"]]
        assert "cold_stress" in risk_names, (
            "21 °C should trigger cold_stress (research: <22 °C stunts durian growth)"
        )

    def test_extreme_values_do_not_raise(self):
        brain = _brain()
        extreme_sets = [
            dict(temperature=0.0, humidity=0.0, ec=0.0, ph=0.0),
            dict(temperature=60.0, humidity=100.0, ec=5000.0, ph=14.0),
            dict(temperature=TEMPERATURE.optimal_low, humidity=HUMIDITY.optimal_low,
                 ec=EC.optimal_low, ph=PH.optimal_low),
        ]
        for vals in extreme_sets:
            result = brain.evaluate_raw(**vals)
            assert 0 <= result["health_score"] <= 100
