"""Phase 5 — Agent Orchestrator.

Runs all five specialist agents, aggregates findings, deduplicates
recommendations, ranks by confidence, and returns a unified result dict
ready for ``OrchardReport`` and the public ``OrchardBrain`` API.
"""
from __future__ import annotations

from dataclasses import dataclass

from ._agent_base import AgentAssessment, RecommendationDict, RiskDict
from .causal_engine import CausalChain, CausalEngine
from .disease_agent import DiseaseAgent
from .flowering_agent import FloweringAgent
from .nutrition_agent import NutritionAgent
from .orchard_graph import OrchardGraph
from .orchard_memory import OrchardMemory, SensorSnapshot, TrendResult
from .water_agent import WaterAgent
from .yield_agent import YieldAgent


@dataclass
class OrchestratorResult:
    """Aggregated output of all agents + supporting intelligence modules."""
    snapshot: SensorSnapshot
    trends: list[TrendResult]
    agent_assessments: list[AgentAssessment]
    causal_chains: list[CausalChain]
    ranked_recommendations: list[RecommendationDict]
    aggregated_risks: list[RiskDict]
    overall_status: str            # "ok" | "warning" | "critical"
    overall_confidence: float      # 0.0 – 1.0
    knowledge_paths: dict[str, list[str]]  # key → explained path


_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class OrchardOrchestrator:
    """Run all agents and produce a consolidated orchard intelligence report.

    Usage::

        orchestrator = OrchardOrchestrator()
        result = orchestrator.run(snapshot, memory=memory)
    """

    def __init__(self) -> None:
        self._water     = WaterAgent()
        self._disease   = DiseaseAgent()
        self._nutrition = NutritionAgent()
        self._flowering = FloweringAgent()
        self._yield     = YieldAgent()
        self._causal    = CausalEngine()
        self._graph     = OrchardGraph()

    # ─────────────────────────────────────────────────────── public API

    def run(
        self,
        snapshot: SensorSnapshot,
        memory: OrchardMemory | None = None,
    ) -> OrchestratorResult:
        """Execute the full pipeline and return an OrchestratorResult."""

        # 1. Persist snapshot & detect trends
        if memory is not None:
            memory.save_snapshot(snapshot)
            trends = memory.detect_trends()
        else:
            trends = []

        # 2. Run all agents
        assessments: list[AgentAssessment] = [
            self._water.assess(snapshot, trends),
            self._disease.assess(snapshot, trends),
            self._nutrition.assess(snapshot, trends),
            self._flowering.assess(snapshot, trends),
            self._yield.assess(snapshot, trends),
        ]

        # 3. Build causal chains
        observations = {
            "temperature": snapshot.temperature,
            "humidity":    snapshot.humidity,
            "ec":          snapshot.ec,
            "ph":          snapshot.ph,
            "vpd_kpa":     snapshot.vpd,
            "trends":      [t.trend for t in trends],
        }
        chains = self._causal.build_reasoning_chain(observations)

        # 4. Aggregate risks (deduplicated by risk identifier)
        aggregated_risks = _deduplicate_risks(
            [r for a in assessments for r in a["risks"]]
        )

        # 5. Aggregate & rank recommendations
        all_recs = [r for a in assessments for r in a["recommendations"]]
        ranked_recs = _deduplicate_and_rank(all_recs)

        # 6. Overall status
        overall_status = _overall_status(assessments)

        # 7. Overall confidence
        overall_conf = (
            max(a["confidence"] for a in assessments) if assessments else 0.0
        )

        # 8. Knowledge graph paths for key relationships
        key_paths = {
            "temperature → yield":     self._graph.explain_path("temperature", "yield"),
            "soil_moisture → yield":   self._graph.explain_path("soil_moisture", "yield"),
            "soil_moisture → phytophthora": self._graph.explain_path("soil_moisture", "phytophthora"),
            "vpd → fruit_drop":        self._graph.explain_path("vpd", "fruit_drop"),
        }

        return OrchestratorResult(
            snapshot=snapshot,
            trends=trends,
            agent_assessments=assessments,
            causal_chains=chains,
            ranked_recommendations=ranked_recs,
            aggregated_risks=aggregated_risks,
            overall_status=overall_status,
            overall_confidence=round(overall_conf, 2),
            knowledge_paths=key_paths,
        )


# ─────────────────────────────────────────────────────── helpers


def _deduplicate_risks(risks: list[RiskDict]) -> list[RiskDict]:
    """Keep only the highest-severity entry for each risk identifier."""
    severity_rank = {"critical": 0, "warning": 1}
    best: dict[str, RiskDict] = {}
    for r in risks:
        key = r["risk"]
        if key not in best or severity_rank[r["severity"]] < severity_rank[best[key]["severity"]]:
            best[key] = r
    result = list(best.values())
    result.sort(key=lambda r: (severity_rank[r["severity"]], r["risk"]))
    return result


def _deduplicate_and_rank(recs: list[RecommendationDict]) -> list[RecommendationDict]:
    """Deduplicate by action key; sort by priority then confidence (desc)."""
    seen: set[str] = set()
    unique: list[RecommendationDict] = []
    for rec in recs:
        key = rec["action"]
        if key not in seen:
            seen.add(key)
            unique.append(rec)

    unique.sort(key=lambda r: (
        _PRIORITY_ORDER.get(r.get("priority", "low"), 3),
        -r.get("confidence", 0.0),
    ))
    return unique


def _overall_status(assessments: list[AgentAssessment]) -> str:
    statuses = {a["status"] for a in assessments}
    if "critical" in statuses:
        return "critical"
    if "warning" in statuses:
        return "warning"
    return "ok"
