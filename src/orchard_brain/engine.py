"""OrchardBrain — public facade that composes all assessors and the full
intelligence pipeline.

This is the single entry point for the orchard_brain package.  Callers
(e.g. RulesEngine, future REST endpoint, or a monitoring loop) should
import and use only this class.

Usage — simple (existing contract, unchanged)
─────────────────────────────────────────────
    from src.orchard_brain import OrchardBrain

    brain = OrchardBrain()          # stateless; one instance is enough
    result = brain.evaluate(reading)
    # or
    result = brain.evaluate_raw(temperature=28.5, humidity=55.0, ec=200.0, ph=6.3)

    print(result)
    # {
    #     "health_score": 94,
    #     "water_stress": 0,
    #     "nutrient_stress": 0,
    #     "risks": [],
    #     "recommendations": [{"action": "maintain_current_conditions", ...}]
    # }

Usage — full intelligence pipeline (Phase 7 integration)
─────────────────────────────────────────────────────────
    brain = OrchardBrain()
    text_report = brain.evaluate_full(reading)      # returns human-readable str
    # or get the structured result:
    orch_result = brain.evaluate_orchestrated(reading)

    # With temporal memory (persist snapshots across calls):
    brain = OrchardBrain(enable_memory=True)
    for reading in sensor_stream:
        text_report = brain.evaluate_full(reading)

Compatibility note
──────────────────
``OrchardBrain`` does NOT import ``SensorReading`` at module level so that
the orchard_brain package remains importable in isolation (e.g. in unit tests
that do not have the full src package on the path).  The ``evaluate`` method
accepts any object with ``.temperature``, ``.humidity``, ``.ec``, ``.ph``
attributes, making it forward-compatible with future sensor models.
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict

from .health import HealthAssessment, HealthResult
from .orchard_memory import OrchardMemory, SensorSnapshot
from .orchard_orchestrator import OrchardOrchestrator, OrchestratorResult
from .orchard_report import OrchardReport
from .recommendation import Recommendation, RecommendationEngine
from .risk import Risk, RiskAssessment
from .knowledge.threshold_engine import ThresholdEngine, ThresholdMap
from database.config import AsyncSessionLocal
from database.threshold_repository import ThresholdRepository


class BrainResult(TypedDict):
    health_score: int
    water_stress: int
    nutrient_stress: int
    risks: list[Risk]
    recommendations: list[Recommendation]


class OrchardBrain:
    """Stateless facade — safe to share across threads.

    Parameters
    ──────────
    enable_memory : bool
        When True, a persistent ``OrchardMemory`` instance is maintained
        across calls so trend detection improves over time.  Default False
        (stateless mode — compatible with the original API contract).
    """

    def __init__(self, enable_memory: bool = False) -> None:
        self._health = HealthAssessment()
        self._risk = RiskAssessment()
        self._rec = RecommendationEngine()
        self._orchestrator = OrchardOrchestrator()
        self._report_gen = OrchardReport()
        self._memory: Optional[OrchardMemory] = OrchardMemory() if enable_memory else None

    # ──────────────────────────────────────────────── original API (unchanged)

    def evaluate(self, reading: Any, thresholds: Optional[ThresholdMap] = None) -> BrainResult:
        """Evaluate a ``SensorReading`` (or any compatible object).

        Args:
            reading: Object exposing ``.temperature``, ``.humidity``,
                     ``.ec``, and ``.ph`` as floats.
            thresholds: Optional pre-resolved thresholds.

        Returns:
            ``BrainResult`` dict — JSON-serialisable with no extra work.
        """
        return self.evaluate_raw(
            temperature=float(reading.temperature),
            humidity=float(reading.humidity),
            ec=float(reading.ec),
            ph=float(reading.ph),
            thresholds=thresholds
        )

    async def evaluate_async(self, reading: Any, epoch_id: Optional[int] = None) -> BrainResult:
        """Async entry point. Resolves dynamic thresholds before synchronous execution."""
        async with AsyncSessionLocal() as session:
            repo = ThresholdRepository(session)
            engine = ThresholdEngine(repo)
            thresholds = await engine.get_all_thresholds(epoch_id)
        
        return self.evaluate(reading, thresholds=thresholds)

    def evaluate_raw(
        self,
        temperature: float,
        humidity: float,
        ec: float,
        ph: float,
        thresholds: Optional[ThresholdMap] = None,
    ) -> BrainResult:
        """Evaluate raw sensor values directly.

        Useful for testing, CLI tools, or callers that do not construct
        a ``SensorReading`` object.
        """
        health: HealthResult = self._health.assess(temperature, humidity, ec, ph, thresholds=thresholds)
        risks: list[Risk] = self._risk.assess(temperature, humidity, ec, ph, thresholds=thresholds)
        recs: list[Recommendation] = self._rec.recommend(
            temperature, humidity, ec, ph,
            health_result=health,
            risks=risks,
            thresholds=thresholds,
        )

        return BrainResult(
            health_score=health.health_score,
            water_stress=health.water_stress,
            nutrient_stress=health.nutrient_stress,
            risks=risks,
            recommendations=recs,
        )

    # ──────────────────────────────────────────────── full intelligence pipeline

    def evaluate_orchestrated(
        self,
        reading: Any,
        memory: Optional[OrchardMemory] = None,
        thresholds: Optional[ThresholdMap] = None,
    ) -> OrchestratorResult:
        """Run the full multi-agent intelligence pipeline.

        Phase 7 integration:
          Sensor Data → Memory → Trend Analysis → Knowledge Graph
          → Multi Agents → Causal Engine → OrchestratorResult

        Args:
            reading : Object with .temperature, .humidity, .ec, .ph attributes.
            memory  : Optional external OrchardMemory instance.  If None, uses
                      the instance's internal memory (if enable_memory=True) or
                      creates a single-shot memory for this call.
            thresholds: Optional pre-resolved thresholds.

        Returns:
            ``OrchestratorResult`` — structured output of all agents and modules.
        """
        snapshot = SensorSnapshot.from_reading(reading)
        mem = memory or self._memory
        return self._orchestrator.run(snapshot, memory=mem, thresholds=thresholds)

    async def evaluate_orchestrated_async(self, reading: Any, epoch_id: Optional[int] = None) -> OrchestratorResult:
        """Async entry point for full pipeline. Resolves dynamic thresholds before synchronous execution."""
        async with AsyncSessionLocal() as session:
            repo = ThresholdRepository(session)
            engine = ThresholdEngine(repo)
            thresholds = await engine.get_all_thresholds(epoch_id)
            
        return self.evaluate_orchestrated(reading, thresholds=thresholds)

    def evaluate_full(
        self,
        reading: Any,
        memory: Optional[OrchardMemory] = None,
        thresholds: Optional[ThresholdMap] = None,
    ) -> str:
        """Run the full pipeline and return a human-readable report string.

        This is the main entry point for Phase 7.  The report includes:
          - Current health metrics
          - Detected trends
          - Knowledge graph explanations
          - All five agent findings
          - Causal reasoning chains
          - Prioritised action plan
          - Confidence scores

        Args:
            reading : Object with .temperature, .humidity, .ec, .ph attributes.
            memory  : Optional external ``OrchardMemory``.
            thresholds: Optional pre-resolved thresholds.

        Returns:
            Multi-line report string — suitable for logging, email alerts, or
            dashboard display.
        """
        snapshot = SensorSnapshot.from_reading(reading)
        mem = memory or self._memory

        # Run health assessment for the report header
        health = self._health.assess(
            reading.temperature, reading.humidity, reading.ec, reading.ph, thresholds=thresholds
        )

        orch_result = self._orchestrator.run(snapshot, memory=mem, thresholds=thresholds)
        return self._report_gen.generate(orch_result, health_result=health)

    def evaluate_full_raw(
        self,
        temperature: float,
        humidity: float,
        ec: float,
        ph: float,
        memory: Optional[OrchardMemory] = None,
        thresholds: Optional[ThresholdMap] = None,
    ) -> str:
        """Full pipeline accepting raw floats — same as evaluate_full() but
        without a SensorReading object (useful for testing)."""

        class _Reading:
            pass

        r = _Reading()
        r.temperature = temperature
        r.humidity = humidity
        r.ec = ec
        r.ph = ph
        return self.evaluate_full(r, memory=memory, thresholds=thresholds)
