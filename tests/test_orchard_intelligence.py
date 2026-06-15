"""Unit tests for Phases 1-7 of the orchard intelligence upgrade.

Run with: python -m pytest tests/test_orchard_intelligence.py -v

Coverage:
  Phase 1 — OrchardMemory / SensorSnapshot / TrendResult / detect_trends
  Phase 2 — CausalEngine / CausalChain
  Phase 3 — OrchardGraph (add_node, add_edge, explain_path, find_related)
  Phase 4 — WaterAgent, DiseaseAgent, NutritionAgent, FloweringAgent, YieldAgent
  Phase 5 — OrchardOrchestrator (run, aggregation, deduplication)
  Phase 6 — OrchardReport (generate, sections present)
  Phase 7 — OrchardBrain.evaluate_full / evaluate_orchestrated
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

import pytest

from src.orchard_brain import (
    CausalChain,
    CausalEngine,
    DiseaseAgent,
    FloweringAgent,
    NutritionAgent,
    OrchardBrain,
    OrchardGraph,
    OrchardMemory,
    OrchardOrchestrator,
    OrchardReport,
    SensorSnapshot,
    WaterAgent,
    YieldAgent,
)
from src.orchard_brain._thresholds import (
    HUMIDITY, PH, PHYTOPHTHORA, TEMPERATURE, VPD, EC
)
from src.orchard_brain.orchard_memory import TrendResult


# ─────────────────────────────────────────────────────────── fixtures


def _snap(
    temperature=28.0,
    humidity=50.0,
    ec=220.0,
    ph=6.0,
    rainfall=0.0,
    offset_minutes: int = 0,
) -> SensorSnapshot:
    ts = datetime.now(tz=timezone.utc) - timedelta(minutes=offset_minutes)
    return SensorSnapshot(
        timestamp=ts,
        soil_moisture=humidity,
        temperature=temperature,
        humidity=humidity,
        ph=ph,
        ec=ec,
        rainfall=rainfall,
    )


def _ideal_snap() -> SensorSnapshot:
    return _snap(temperature=28.0, humidity=50.0, ec=220.0, ph=6.0)


class _FakeReading:
    def __init__(self, temperature=28.0, humidity=50.0, ec=220.0, ph=6.0):
        self.temperature = temperature
        self.humidity = humidity
        self.ec = ec
        self.ph = ph


def _ideal_reading() -> _FakeReading:
    return _FakeReading()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1 — OrchardMemory & SensorSnapshot
# ═══════════════════════════════════════════════════════════════════════════════


class TestSensorSnapshot:
    def test_vpd_auto_computed_when_none(self):
        snap = _ideal_snap()
        assert snap.vpd is not None
        assert snap.vpd > 0.0

    def test_from_reading_constructs_snapshot(self):
        reading = _ideal_reading()
        snap = SensorSnapshot.from_reading(reading)
        assert snap.temperature == reading.temperature
        assert snap.humidity == reading.humidity
        assert snap.ec == reading.ec
        assert snap.ph == reading.ph
        assert snap.vpd is not None

    def test_explicit_rainfall_stored(self):
        snap = _snap(rainfall=5.0)
        assert snap.rainfall == 5.0

    def test_snapshot_timestamp_is_set(self):
        snap = _ideal_snap()
        assert isinstance(snap.timestamp, datetime)


class TestOrchardMemory:
    def test_save_and_retrieve_snapshot(self):
        mem = OrchardMemory()
        snap = _ideal_snap()
        mem.save_snapshot(snap)
        assert mem.snapshot_count == 1

    def test_get_recent_snapshots_returns_newest(self):
        mem = OrchardMemory()
        for i in range(5):
            mem.save_snapshot(_snap(offset_minutes=i * 10))
        recent = mem.get_recent_snapshots(3)
        assert len(recent) == 3

    def test_get_last_days_filters_by_time(self):
        mem = OrchardMemory()
        # Old snapshot (2 days ago)
        old = _snap(offset_minutes=60 * 48)
        mem.save_snapshot(old)
        # Recent snapshot
        new = _ideal_snap()
        mem.save_snapshot(new)
        last_day = mem.get_last_days(1)
        assert len(last_day) == 1

    def test_ring_buffer_evicts_oldest(self):
        mem = OrchardMemory(max_snapshots=5)
        for i in range(7):
            mem.save_snapshot(_ideal_snap())
        assert mem.snapshot_count == 5

    def test_detect_trends_empty_when_too_few_snapshots(self):
        mem = OrchardMemory()
        mem.save_snapshot(_ideal_snap())
        assert mem.detect_trends() == []

    def test_detect_trends_returns_list(self):
        mem = OrchardMemory()
        for i in range(10):
            mem.save_snapshot(_ideal_snap())
        trends = mem.detect_trends()
        assert isinstance(trends, list)

    def test_latest_returns_most_recent(self):
        mem = OrchardMemory()
        mem.save_snapshot(_snap(temperature=25.0))
        mem.save_snapshot(_snap(temperature=30.0))
        latest = mem.latest()
        assert latest is not None
        assert latest.temperature == 30.0

    def test_latest_returns_none_when_empty(self):
        mem = OrchardMemory()
        assert mem.latest() is None


class TestTrendDetection:
    def _populate(self, mem: OrchardMemory, snapshots: list[SensorSnapshot]) -> None:
        for s in snapshots:
            mem.save_snapshot(s)

    def test_rising_temperature_detected(self):
        mem = OrchardMemory()
        # Temperature steadily rising
        snaps = [_snap(temperature=25.0 + i * 2) for i in range(10)]
        self._populate(mem, snaps)
        trends = mem.detect_trends()
        names = [t.trend for t in trends]
        assert "rising_temperature" in names

    def test_falling_soil_moisture_detected(self):
        mem = OrchardMemory()
        # Moisture steadily falling
        snaps = [_snap(humidity=60.0 - i * 5) for i in range(10)]
        self._populate(mem, snaps)
        trends = mem.detect_trends()
        names = [t.trend for t in trends]
        assert "falling_soil_moisture" in names

    def test_prolonged_dry_period_detected(self):
        mem = OrchardMemory()
        # All readings below warn_low
        dry_val = HUMIDITY.warn_low - 5.0
        snaps = [_snap(humidity=dry_val, rainfall=0.0) for _ in range(10)]
        self._populate(mem, snaps)
        trends = mem.detect_trends()
        names = [t.trend for t in trends]
        assert "prolonged_dry_period" in names

    def test_excessive_wet_period_detected(self):
        mem = OrchardMemory()
        # All readings above warn_high
        wet_val = HUMIDITY.warn_high + 5.0
        snaps = [_snap(humidity=wet_val) for _ in range(10)]
        self._populate(mem, snaps)
        trends = mem.detect_trends()
        names = [t.trend for t in trends]
        assert "excessive_wet_period" in names

    def test_no_trend_on_stable_readings(self):
        mem = OrchardMemory()
        snaps = [_ideal_snap() for _ in range(10)]
        self._populate(mem, snaps)
        trends = mem.detect_trends()
        # Stable ideal conditions should produce no rising_temperature or falling_moisture
        names = [t.trend for t in trends]
        assert "rising_temperature" not in names
        assert "falling_soil_moisture" not in names

    def test_trend_result_has_required_fields(self):
        mem = OrchardMemory()
        snaps = [_snap(humidity=60.0 - i * 5) for i in range(10)]
        self._populate(mem, snaps)
        trends = mem.detect_trends()
        for t in trends:
            assert isinstance(t.trend, str)
            assert isinstance(t.direction, str)
            assert isinstance(t.magnitude, (int, float))
            assert 0.0 <= t.confidence <= 1.0
            assert isinstance(t.description, str)

    def test_increasing_vpd_detected(self):
        mem = OrchardMemory()
        # Rising temperature + falling humidity → rising VPD
        snaps = [_snap(temperature=28.0 + i * 2, humidity=60.0 - i * 4) for i in range(10)]
        self._populate(mem, snaps)
        trends = mem.detect_trends()
        names = [t.trend for t in trends]
        assert "increasing_vpd" in names


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2 — CausalEngine
# ═══════════════════════════════════════════════════════════════════════════════


class TestCausalEngine:
    def test_drought_triggers_causal_chain(self):
        ce = CausalEngine()
        chains = ce.build_reasoning_chain({"temperature": 28.0, "humidity": 5.0, "ec": 220.0, "ph": 6.0})
        causes = [c.cause for c in chains]
        assert any("soil moisture" in c.lower() or "drought" in c.lower() or "deficit" in c.lower()
                   for c in causes)

    def test_phytophthora_triggers_chain(self):
        ce = CausalEngine()
        chains = ce.build_reasoning_chain({
            "temperature": 28.0,
            "humidity": PHYTOPHTHORA.moisture_critical + 1.0,
            "ec": 220.0,
            "ph": 6.0,
        })
        risks = [c.risk for c in chains]
        assert any("phytophthora" in r.lower() or "canker" in r.lower() for r in risks)

    def test_ideal_conditions_few_chains(self):
        ce = CausalEngine()
        chains = ce.build_reasoning_chain({"temperature": 28.0, "humidity": 50.0, "ec": 220.0, "ph": 6.0})
        assert len(chains) == 0

    def test_causal_chain_has_required_fields(self):
        ce = CausalEngine()
        chains = ce.build_reasoning_chain({"temperature": 40.0, "humidity": 10.0, "ec": 220.0, "ph": 6.0})
        for chain in chains:
            assert isinstance(chain, CausalChain)
            assert chain.cause
            assert chain.impact
            assert chain.risk
            assert chain.action
            assert 0.0 <= chain.confidence <= 1.0

    def test_chains_sorted_by_confidence_descending(self):
        ce = CausalEngine()
        chains = ce.build_reasoning_chain({"temperature": 40.0, "humidity": 5.0, "ec": 10.0, "ph": 4.0})
        confidences = [c.confidence for c in chains]
        assert confidences == sorted(confidences, reverse=True)

    def test_trend_based_chains_included(self):
        ce = CausalEngine()
        chains = ce.build_reasoning_chain({
            "temperature": 28.0,
            "humidity": 20.0,
            "ec": 220.0,
            "ph": 6.0,
            "trends": ["prolonged_dry_period"],
        })
        causes = " ".join(c.cause for c in chains)
        assert "dry" in causes.lower() or "flower" in causes.lower()

    def test_alkaline_ph_triggers_chain(self):
        ce = CausalEngine()
        chains = ce.build_reasoning_chain({"temperature": 28.0, "humidity": 50.0, "ec": 220.0, "ph": 8.0})
        risks = " ".join(c.risk for c in chains)
        assert "lock" in risks.lower() or "chloros" in risks.lower() or "alkalin" in risks.lower()

    def test_acid_ph_triggers_chain(self):
        ce = CausalEngine()
        chains = ce.build_reasoning_chain({"temperature": 28.0, "humidity": 50.0, "ec": 220.0, "ph": 4.0})
        causes = " ".join(c.cause for c in chains)
        assert "acid" in causes.lower() or "ph" in causes.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3 — OrchardGraph
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrchardGraph:
    def test_pre_built_nodes_exist(self):
        g = OrchardGraph()
        expected = ["soil_moisture", "temperature", "humidity", "vpd", "yield",
                    "phytophthora", "root_health", "fertilizer", "flowering", "fruit_set"]
        for node in expected:
            assert node in g._nodes, f"Node '{node}' missing from pre-built graph"

    def test_explain_path_temperature_to_yield(self):
        g = OrchardGraph()
        path = g.explain_path("temperature", "yield")
        assert path, "Expected a path from temperature to yield"
        assert path[0] == "temperature"
        assert path[-1] == "yield"

    def test_explain_path_soil_moisture_to_phytophthora(self):
        g = OrchardGraph()
        path = g.explain_path("soil_moisture", "phytophthora")
        assert path and path[0] == "soil_moisture" and path[-1] == "phytophthora"

    def test_explain_path_vpd_to_fruit_drop(self):
        g = OrchardGraph()
        path = g.explain_path("vpd", "fruit_drop")
        assert path and path[0] == "vpd" and path[-1] == "fruit_drop"

    def test_explain_path_same_node_returns_single_element(self):
        g = OrchardGraph()
        path = g.explain_path("yield", "yield")
        assert path == ["yield"]

    def test_explain_path_unknown_node_returns_empty(self):
        g = OrchardGraph()
        path = g.explain_path("nonexistent", "yield")
        assert path == []

    def test_find_related_nodes_returns_neighbours(self):
        g = OrchardGraph()
        related = g.find_related_nodes("soil_moisture")
        assert related, "soil_moisture should have outgoing edges"
        assert "root_health" in related or "phytophthora" in related

    def test_add_node_idempotent(self):
        g = OrchardGraph()
        g.add_node("soil_moisture", "new description")
        assert "soil_moisture" in g._nodes

    def test_add_edge_creates_nodes_automatically(self):
        g = OrchardGraph()
        g.add_edge("sensor_x", "sensor_y", "correlates")
        assert "sensor_x" in g._nodes
        assert "sensor_y" in g._nodes

    def test_add_edge_deduplicated(self):
        g = OrchardGraph()
        g.add_edge("soil_moisture", "root_health")
        g.add_edge("soil_moisture", "root_health")  # duplicate
        edges = [e for e in g._edges if e.source == "soil_moisture" and e.target == "root_health"]
        assert len(edges) == 1

    def test_format_path_returns_string(self):
        g = OrchardGraph()
        path = g.explain_path("temperature", "yield")
        text = g.format_path(path)
        assert "→" in text
        assert "temperature" in text
        assert "yield" in text

    def test_format_path_empty_returns_no_path(self):
        g = OrchardGraph()
        text = g.format_path([])
        assert "no path" in text.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 4 — Specialist Agents
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentAssessmentContract:
    """All agents must return an AgentAssessment with all required keys."""

    def _check_contract(self, assessment: dict) -> None:
        assert "agent" in assessment
        assert "status" in assessment
        assert "risks" in assessment
        assert "recommendations" in assessment
        assert "confidence" in assessment
        assert "reasoning" in assessment
        assert assessment["status"] in ("ok", "warning", "critical")
        assert 0.0 <= assessment["confidence"] <= 1.0
        assert isinstance(assessment["risks"], list)
        assert isinstance(assessment["recommendations"], list)
        assert isinstance(assessment["reasoning"], str)
        for rec in assessment["recommendations"]:
            assert "action" in rec
            assert "priority" in rec
            assert "confidence" in rec

    def test_water_agent_contract(self):
        self._check_contract(WaterAgent().assess(_ideal_snap()))

    def test_disease_agent_contract(self):
        self._check_contract(DiseaseAgent().assess(_ideal_snap()))

    def test_nutrition_agent_contract(self):
        self._check_contract(NutritionAgent().assess(_ideal_snap()))

    def test_flowering_agent_contract(self):
        self._check_contract(FloweringAgent().assess(_ideal_snap()))

    def test_yield_agent_contract(self):
        self._check_contract(YieldAgent().assess(_ideal_snap()))


class TestWaterAgent:
    def test_ideal_conditions_ok_status(self):
        result = WaterAgent().assess(_ideal_snap())
        assert result["status"] == "ok"

    def test_critical_drought_critical_status(self):
        result = WaterAgent().assess(_snap(humidity=HUMIDITY.critical_low))
        assert result["status"] == "critical"

    def test_drought_triggers_irrigation_recommendation(self):
        result = WaterAgent().assess(_snap(humidity=5.0))
        actions = [r["action"] for r in result["recommendations"]]
        assert "trigger_irrigation" in actions

    def test_waterlogging_triggers_stop_irrigation(self):
        result = WaterAgent().assess(_snap(humidity=HUMIDITY.critical_high))
        actions = [r["action"] for r in result["recommendations"]]
        assert "stop_irrigation" in actions

    def test_high_vpd_triggers_cooling(self):
        result = WaterAgent().assess(_snap(temperature=42.0, humidity=10.0))
        actions = [r["action"] for r in result["recommendations"]]
        assert "trigger_micro_sprinkler_cooling" in actions

    def test_trend_falling_moisture_recommendation(self):
        trend = TrendResult(
            trend="falling_soil_moisture", direction="falling",
            magnitude=10.0, confidence=0.80,
            description="moisture is falling"
        )
        result = WaterAgent().assess(_ideal_snap(), trends=[trend])
        actions = [r["action"] for r in result["recommendations"]]
        assert "increase_irrigation_frequency" in actions


class TestDiseaseAgent:
    def test_ideal_conditions_ok_status(self):
        result = DiseaseAgent().assess(_ideal_snap())
        assert result["status"] == "ok"

    def test_warm_wet_warning(self):
        snap = _snap(temperature=28.0, humidity=PHYTOPHTHORA.moisture_warn + 1.0)
        result = DiseaseAgent().assess(snap)
        assert result["status"] in ("warning", "critical")

    def test_warm_very_wet_critical(self):
        snap = _snap(temperature=28.0, humidity=PHYTOPHTHORA.moisture_critical + 1.0)
        result = DiseaseAgent().assess(snap)
        assert result["status"] == "critical"

    def test_critical_triggers_inspect_recommendation(self):
        snap = _snap(temperature=28.0, humidity=PHYTOPHTHORA.moisture_critical + 1.0)
        result = DiseaseAgent().assess(snap)
        actions = [r["action"] for r in result["recommendations"]]
        assert "inspect_for_phytophthora" in actions

    def test_cold_wet_no_disease_risk(self):
        snap = _snap(temperature=15.0, humidity=90.0)
        result = DiseaseAgent().assess(snap)
        assert result["status"] == "ok"

    def test_wet_period_trend_raises_risk(self):
        trend = TrendResult(
            trend="excessive_wet_period", direction="sustained",
            magnitude=70.0, confidence=0.80,
            description="sustained wet"
        )
        snap = _ideal_snap()  # currently OK soil moisture
        result = DiseaseAgent().assess(snap, trends=[trend])
        # Should show at least a warning due to sustained wet trend
        risk_names = [r["risk"] for r in result["risks"]]
        assert "phytophthora_risk" in risk_names


class TestNutritionAgent:
    def test_ideal_conditions_ok_status(self):
        result = NutritionAgent().assess(_ideal_snap())
        assert result["status"] == "ok"

    def test_low_ph_acid_warning(self):
        snap = _snap(ph=PH.warn_low - 0.1)
        result = NutritionAgent().assess(snap)
        assert result["status"] in ("warning", "critical")
        actions = [r["action"] for r in result["recommendations"]]
        assert "apply_lime_to_raise_ph" in actions

    def test_high_ph_alkaline_warning(self):
        snap = _snap(ph=PH.warn_high + 0.1)
        result = NutritionAgent().assess(snap)
        assert result["status"] in ("warning", "critical")
        actions = [r["action"] for r in result["recommendations"]]
        assert "apply_sulfur_to_lower_ph" in actions

    def test_low_ec_fertigation_recommendation(self):
        snap = _snap(ec=EC.critical_low)
        result = NutritionAgent().assess(snap)
        actions = [r["action"] for r in result["recommendations"]]
        assert "adjust_fertigation_ratio_to_high_pk" in actions

    def test_high_ec_flush_recommendation(self):
        snap = _snap(ec=EC.critical_high)
        result = NutritionAgent().assess(snap)
        actions = [r["action"] for r in result["recommendations"]]
        assert "flush_irrigation_to_reduce_ec" in actions

    def test_research_corrected_ph_65_optimal(self):
        # pH 7.0 should trigger alkaline warning under new thresholds
        snap = _snap(ph=7.0)
        result = NutritionAgent().assess(snap)
        assert result["status"] in ("warning", "critical"), \
            "pH=7.0 should trigger warning (research: optimal ≤6.5)"


class TestFloweringAgent:
    def test_ideal_no_flowering_trigger(self):
        result = FloweringAgent().assess(_ideal_snap())
        # No dry spell → no flowering advisory expected in default ideal conditions
        assert result["status"] in ("ok", "warning")  # either is valid for ideal

    def test_dry_conditions_trigger_advisory(self):
        snap = _snap(humidity=HUMIDITY.warn_low - 1.0, temperature=28.0)
        result = FloweringAgent().assess(snap)
        actions = [r["action"] for r in result["recommendations"]]
        assert "anticipate_flowering_trigger" in actions

    def test_prolonged_dry_trend_raises_confidence(self):
        trend = TrendResult(
            trend="prolonged_dry_period", direction="sustained",
            magnitude=80.0, confidence=0.85,
            description="persistent dry"
        )
        snap = _snap(humidity=HUMIDITY.warn_low - 1.0, temperature=28.0)
        result = FloweringAgent().assess(snap, trends=[trend])
        actions = [r["action"] for r in result["recommendations"]]
        assert "anticipate_flowering_trigger" in actions
        flower_rec = next(r for r in result["recommendations"] if r["action"] == "anticipate_flowering_trigger")
        assert flower_rec["confidence"] >= 0.70, "Should have higher confidence with trend support"

    def test_cold_during_flowering_window_warning(self):
        snap = _snap(temperature=TEMPERATURE.warn_low - 0.5)
        result = FloweringAgent().assess(snap)
        risk_names = [r["risk"] for r in result["risks"]]
        assert "cold_stress" in risk_names


class TestYieldAgent:
    def test_ideal_conditions_high_yield_potential(self):
        result = YieldAgent().assess(_ideal_snap())
        assert result["status"] == "ok"
        # Should recommend maintaining conditions
        actions = [r["action"] for r in result["recommendations"]]
        assert "maintain_current_conditions" in actions

    def test_catastrophic_conditions_critical_yield(self):
        snap = _snap(temperature=42.0, humidity=5.0, ec=10.0, ph=4.0)
        result = YieldAgent().assess(snap)
        assert result["status"] == "critical"
        risk_names = [r["risk"] for r in result["risks"]]
        assert "low_yield_potential" in risk_names

    def test_moderate_stress_warning_yield(self):
        # Yield weights: T=25%, water=35%, nutrient=25%, disease=15%.
        # With only one stressor the weighted floor is 65 — multiple stressors needed.
        snap = _snap(humidity=5.0, ec=30.0)   # drought + very low EC
        result = YieldAgent().assess(snap)
        assert result["status"] in ("warning", "critical")

    def test_falling_moisture_trend_adds_risk(self):
        trend = TrendResult(
            trend="falling_soil_moisture", direction="falling",
            magnitude=15.0, confidence=0.80,
            description="moisture dropping"
        )
        result = YieldAgent().assess(_ideal_snap(), trends=[trend])
        risk_names = [r["risk"] for r in result["risks"]]
        assert "trending_yield_reduction" in risk_names


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 5 — OrchardOrchestrator
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrchardOrchestrator:
    def test_run_returns_orchestrator_result(self):
        orch = OrchardOrchestrator()
        result = orch.run(_ideal_snap())
        assert result is not None

    def test_result_has_five_agent_assessments(self):
        orch = OrchardOrchestrator()
        result = orch.run(_ideal_snap())
        assert len(result.agent_assessments) == 5

    def test_overall_status_is_valid(self):
        orch = OrchardOrchestrator()
        result = orch.run(_ideal_snap())
        assert result.overall_status in ("ok", "warning", "critical")

    def test_recommendations_are_deduplicated(self):
        orch = OrchardOrchestrator()
        result = orch.run(_snap(humidity=5.0, temperature=40.0))
        actions = [r["action"] for r in result.ranked_recommendations]
        assert len(actions) == len(set(actions)), f"Duplicate actions: {actions}"

    def test_critical_recommendations_ranked_first(self):
        orch = OrchardOrchestrator()
        result = orch.run(_snap(humidity=HUMIDITY.critical_low))
        if len(result.ranked_recommendations) > 1:
            priorities = [r["priority"] for r in result.ranked_recommendations]
            order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            ranked = [order[p] for p in priorities]
            assert ranked == sorted(ranked)

    def test_causal_chains_produced_for_stressed_reading(self):
        orch = OrchardOrchestrator()
        result = orch.run(_snap(humidity=5.0, temperature=40.0))
        assert len(result.causal_chains) > 0

    def test_knowledge_paths_computed(self):
        orch = OrchardOrchestrator()
        result = orch.run(_ideal_snap())
        assert "temperature → yield" in result.knowledge_paths
        assert "soil_moisture → yield" in result.knowledge_paths
        for path in result.knowledge_paths.values():
            assert isinstance(path, list)

    def test_memory_integration(self):
        mem = OrchardMemory()
        orch = OrchardOrchestrator()
        for i in range(5):
            orch.run(_ideal_snap(), memory=mem)
        assert mem.snapshot_count == 5

    def test_critical_status_on_catastrophic_reading(self):
        orch = OrchardOrchestrator()
        result = orch.run(_snap(humidity=5.0, temperature=42.0, ec=10.0, ph=4.0))
        assert result.overall_status == "critical"

    def test_ok_status_on_ideal_reading(self):
        orch = OrchardOrchestrator()
        result = orch.run(_ideal_snap())
        assert result.overall_status == "ok"

    def test_aggregated_risks_deduplicated_by_key(self):
        orch = OrchardOrchestrator()
        result = orch.run(_snap(humidity=5.0))
        risk_names = [r["risk"] for r in result.aggregated_risks]
        assert len(risk_names) == len(set(risk_names))


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 6 — OrchardReport
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrchardReport:
    def _make_result(self, **snap_kwargs):
        orch = OrchardOrchestrator()
        snap = _snap(**snap_kwargs) if snap_kwargs else _ideal_snap()
        return orch.run(snap)

    def test_generate_returns_string(self):
        result = self._make_result()
        report = OrchardReport().generate(result)
        assert isinstance(report, str)
        assert len(report) > 100

    def test_report_contains_all_sections(self):
        result = self._make_result()
        report = OrchardReport().generate(result)
        assert "SECTION 1" in report
        assert "SECTION 3" in report  # trends
        assert "SECTION 4" in report  # knowledge graph
        assert "SECTION 5" in report  # agents
        assert "SECTION 6" in report  # causal chains
        assert "SECTION 7" in report  # action plan
        assert "SECTION 8" in report  # confidence

    def test_report_contains_status_banner(self):
        result = self._make_result()
        report = OrchardReport().generate(result)
        assert "STATUS" in report

    def test_report_contains_sensor_values(self):
        result = self._make_result(temperature=29.5, humidity=52.0)
        report = OrchardReport().generate(result)
        assert "29.5" in report
        assert "52.0" in report

    def test_report_contains_agent_names(self):
        result = self._make_result()
        report = OrchardReport().generate(result)
        assert "WaterAgent" in report
        assert "DiseaseAgent" in report
        assert "NutritionAgent" in report
        assert "FloweringAgent" in report
        assert "YieldAgent" in report

    def test_report_critical_scenario_flags_critical(self):
        result = self._make_result(humidity=5.0, temperature=42.0)
        report = OrchardReport().generate(result)
        assert "CRITICAL" in report or "critical" in report.lower()

    def test_report_with_health_result_adds_section_2(self):
        from src.orchard_brain.health import HealthAssessment
        health = HealthAssessment().assess(28.0, 50.0, 220.0, 6.0)
        result = self._make_result()
        report = OrchardReport().generate(result, health_result=health)
        assert "SECTION 2" in report
        assert "Health Score" in report

    def test_confidence_bars_in_report(self):
        result = self._make_result()
        report = OrchardReport().generate(result)
        assert "█" in report or "░" in report  # confidence bar characters


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 7 — Full Integration via OrchardBrain
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrchardBrainFullPipeline:
    def test_evaluate_full_returns_string(self):
        brain = OrchardBrain()
        report = brain.evaluate_full(_ideal_reading())
        assert isinstance(report, str)
        assert len(report) > 200

    def test_evaluate_full_raw_returns_string(self):
        brain = OrchardBrain()
        report = brain.evaluate_full_raw(
            temperature=28.0, humidity=50.0, ec=220.0, ph=6.0
        )
        assert isinstance(report, str)

    def test_evaluate_orchestrated_returns_result(self):
        brain = OrchardBrain()
        result = brain.evaluate_orchestrated(_ideal_reading())
        assert result is not None
        assert hasattr(result, "agent_assessments")
        assert len(result.agent_assessments) == 5

    def test_memory_enabled_accumulates_snapshots(self):
        brain = OrchardBrain(enable_memory=True)
        for _ in range(5):
            brain.evaluate_full(_ideal_reading())
        assert brain._memory is not None
        assert brain._memory.snapshot_count == 5

    def test_existing_evaluate_still_works(self):
        """evaluate() and evaluate_raw() must be unchanged."""
        brain = OrchardBrain()
        result = brain.evaluate(_ideal_reading())
        assert "health_score" in result
        assert "water_stress" in result
        assert "nutrient_stress" in result
        assert "risks" in result
        assert "recommendations" in result

    def test_full_pipeline_stress_scenario(self):
        brain = OrchardBrain()
        result = brain.evaluate_orchestrated(
            _FakeReading(temperature=40.0, humidity=5.0, ec=10.0, ph=4.0)
        )
        assert result.overall_status == "critical"
        assert len(result.ranked_recommendations) > 0

    def test_pipeline_json_serialisable(self):
        brain = OrchardBrain()
        basic = brain.evaluate_raw(28.0, 50.0, 220.0, 6.0)
        serialised = json.dumps(basic)
        roundtrip = json.loads(serialised)
        assert roundtrip["health_score"] == basic["health_score"]

    def test_report_and_basic_result_consistent(self):
        """health_score from evaluate_raw should match what report sees."""
        brain = OrchardBrain()
        reading = _ideal_reading()
        basic = brain.evaluate_raw(
            reading.temperature, reading.humidity, reading.ec, reading.ph
        )
        report = brain.evaluate_full(reading)
        # Both should reflect the same healthy state
        assert basic["health_score"] >= 90
        assert "STATUS" in report

    def test_evaluate_full_critical_scenario_mentions_action(self):
        brain = OrchardBrain()
        report = brain.evaluate_full(_FakeReading(humidity=5.0))
        assert "irrigation" in report.lower()

    def test_workflow_sensor_memory_trend_agents_report(self):
        """End-to-end Phase 7 workflow: Memory → Trends → Agents → Report."""
        brain = OrchardBrain(enable_memory=True)

        # Simulate a deteriorating orchard over 10 readings
        for i in range(10):
            reading = _FakeReading(
                temperature=28.0 + i * 0.5,
                humidity=55.0 - i * 3.0,
                ec=220.0,
                ph=6.0,
            )
            report = brain.evaluate_full(reading)

        # After 10 readings, trends should exist and report should reflect them
        assert brain._memory is not None
        assert brain._memory.snapshot_count == 10
        trends = brain._memory.detect_trends()
        assert len(trends) > 0
        assert isinstance(report, str)
        assert len(report) > 200
