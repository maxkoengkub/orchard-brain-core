"""orchard_brain — explainable orchard intelligence engine for Smart Durian Orchard.

Public API — simple (original contract, unchanged)
──────────────────────────────────────────────────
    from src.orchard_brain import OrchardBrain

    brain = OrchardBrain()
    result = brain.evaluate(sensor_reading)          # returns BrainResult dict
    result = brain.evaluate_raw(temperature=28.5, humidity=55.0, ec=200.0, ph=6.3)

Public API — full intelligence pipeline (Phase 7)
─────────────────────────────────────────────────
    brain = OrchardBrain(enable_memory=True)         # persistent trend memory
    report = brain.evaluate_full(sensor_reading)     # human-readable report str
    orch   = brain.evaluate_orchestrated(sensor_reading)  # OrchestratorResult

Modules
───────
    engine               OrchardBrain  — primary facade
    health               HealthAssessment
    risk                 RiskAssessment
    recommendation       RecommendationEngine

    orchard_memory       OrchardMemory, SensorSnapshot, TrendResult  (Phase 1)
    causal_engine        CausalEngine, CausalChain                   (Phase 2)
    orchard_graph        OrchardGraph                                 (Phase 3)
    water_agent          WaterAgent                                   (Phase 4)
    disease_agent        DiseaseAgent                                 (Phase 4)
    nutrition_agent      NutritionAgent                               (Phase 4)
    flowering_agent      FloweringAgent                               (Phase 4)
    yield_agent          YieldAgent                                   (Phase 4)
    orchard_orchestrator OrchardOrchestrator, OrchestratorResult     (Phase 5)
    orchard_report       OrchardReport                                (Phase 6)
    _thresholds          Agronomic constants (internal; import for tests only)
"""
# ── Original API (Phase 1-3 of first implementation — unchanged)
# ── Intelligence pipeline (Phases 1-7 of upgrade)
from ._agent_base import AgentAssessment
from .causal_engine import CausalChain, CausalEngine
from .disease_agent import DiseaseAgent
from .engine import BrainResult, OrchardBrain
from .flowering_agent import FloweringAgent
from .health import HealthAssessment, HealthResult
from .nutrition_agent import NutritionAgent
from .orchard_graph import OrchardGraph
from .orchard_memory import OrchardMemory, SensorSnapshot, TrendResult
from .orchard_orchestrator import OrchardOrchestrator, OrchestratorResult
from .orchard_report import OrchardReport
from .recommendation import Recommendation, RecommendationEngine
from .risk import Risk, RiskAssessment
from .water_agent import WaterAgent
from .yield_agent import YieldAgent

__all__ = [
    # Core facade
    "OrchardBrain",
    "BrainResult",
    # Assessors
    "HealthAssessment",
    "HealthResult",
    "RiskAssessment",
    "Risk",
    "RecommendationEngine",
    "Recommendation",
    # Phase 1 — Temporal Memory
    "OrchardMemory",
    "SensorSnapshot",
    "TrendResult",
    # Phase 2 — Causal Engine
    "CausalEngine",
    "CausalChain",
    # Phase 3 — Knowledge Graph
    "OrchardGraph",
    # Phase 4 — Agents
    "AgentAssessment",
    "WaterAgent",
    "DiseaseAgent",
    "NutritionAgent",
    "FloweringAgent",
    "YieldAgent",
    # Phase 5 — Orchestrator
    "OrchardOrchestrator",
    "OrchestratorResult",
    # Phase 6 — Report
    "OrchardReport",
]
