"""Phase 0 hardening tests.

These lock in the backward-compatible resolution of the RH vs soil-moisture
conflation, the threshold split, and the packaging/CLI entry point.  They do
NOT modify or depend on the pre-existing test suite.
"""
from __future__ import annotations

import warnings

import pytest

from src.orchard_brain import OrchardBrain, SensorSnapshot, orchard_memory
from src.orchard_brain._thresholds import (
    HUMIDITY,
    RELATIVE_HUMIDITY,
    SOIL_MOISTURE,
)


class _Reading:
    """Duck-typed sensor reading."""

    def __init__(self, temperature=28.0, humidity=50.0, ec=220.0, ph=6.0):
        self.temperature = temperature
        self.humidity = humidity
        self.ec = ec
        self.ph = ph


# ───────────────────────────────────────────── threshold split / alias


def test_humidity_is_backward_compatible_alias_of_soil_moisture():
    assert HUMIDITY is SOIL_MOISTURE


def test_soil_moisture_bands_are_vwc_values():
    assert SOIL_MOISTURE.optimal_low == 40.0
    assert SOIL_MOISTURE.optimal_high == 60.0
    assert SOIL_MOISTURE.warn_high == 75.0


def test_relative_humidity_bands_are_air_rh_values():
    # Durian air-RH optimum ~75-85 %, distinct from soil VWC.
    assert RELATIVE_HUMIDITY.optimal_low == 75.0
    assert RELATIVE_HUMIDITY.optimal_high == 85.0
    assert RELATIVE_HUMIDITY.optimal_low != SOIL_MOISTURE.optimal_low


# ───────────────────────────────────────────── proxy flag behaviour


def test_from_reading_defaults_to_proxy_and_preserves_behaviour():
    r = _Reading(humidity=52.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        snap = SensorSnapshot.from_reading(r)
    assert snap.soil_moisture_is_proxy is True
    # Default behaviour unchanged: soil_moisture mirrors air humidity.
    assert snap.soil_moisture == 52.0
    assert snap.humidity == 52.0


def test_from_reading_with_explicit_soil_moisture_is_not_proxy():
    r = _Reading(humidity=52.0)
    snap = SensorSnapshot.from_reading(r, soil_moisture=45.0)
    assert snap.soil_moisture_is_proxy is False
    assert snap.soil_moisture == 45.0
    assert snap.humidity == 52.0  # air RH kept distinct


def test_proxy_fallback_emits_one_time_warning():
    orchard_memory._soil_moisture_proxy_warned = False
    try:
        with pytest.warns(UserWarning, match="proxy"):
            SensorSnapshot.from_reading(_Reading())
    finally:
        orchard_memory._soil_moisture_proxy_warned = True


def test_default_snapshot_has_proxy_flag_false_by_default_constructor():
    # Direct construction (used widely in existing tests) defaults to non-proxy.
    from datetime import UTC, datetime

    snap = SensorSnapshot(
        timestamp=datetime.now(tz=UTC),
        soil_moisture=50.0,
        temperature=28.0,
        humidity=50.0,
        ph=6.0,
        ec=220.0,
    )
    assert snap.soil_moisture_is_proxy is False


# ───────────────────────────────────────────── engine passthrough + report


def test_evaluate_full_raw_labels_proxy_by_default():
    brain = OrchardBrain()
    report = brain.evaluate_full_raw(temperature=28.0, humidity=50.0, ec=220.0, ph=6.0)
    assert "proxy" in report.lower()


def test_evaluate_full_with_explicit_soil_moisture_has_no_proxy_label():
    brain = OrchardBrain()
    report = brain.evaluate_full(_Reading(humidity=50.0), soil_moisture=45.0)
    assert "[proxy" not in report


def test_evaluate_orchestrated_accepts_soil_moisture():
    brain = OrchardBrain()
    result = brain.evaluate_orchestrated(_Reading(humidity=50.0), soil_moisture=30.0)
    assert result.snapshot.soil_moisture == 30.0
    assert result.snapshot.soil_moisture_is_proxy is False


# ───────────────────────────────────────────── packaging / CLI


def test_cli_entrypoint_importable_and_runs_json():
    from src.orchard_brain.__main__ import main

    rc = main(["--json", "--temperature", "28", "--humidity", "55", "--ec", "200", "--ph", "6.3"])
    assert rc == 0
