"""Shared base types for the multi-agent system (Phase 4).

All five agents return an ``AgentAssessment``.  Import it from here so
there is exactly one canonical definition.
"""
from __future__ import annotations

from typing import TypedDict


class RiskDict(TypedDict):
    """A single risk finding (same shape as ``risk.Risk``)."""
    risk: str       # identifier, e.g. "drought" | "phytophthora_risk"
    severity: str   # "warning" | "critical"
    message: str    # human-readable explanation with actual values


class RecommendationDict(TypedDict):
    """A single recommendation (same shape as ``recommendation.Recommendation``)."""
    action: str        # action key, e.g. "trigger_irrigation"
    priority: str      # "critical" | "high" | "medium" | "low"
    reason: str        # human-readable justification
    confidence: float  # 0.0 – 1.0


class AgentAssessment(TypedDict):
    """Standardised output produced by every specialist agent.

    Fields
    ──────
    agent           Identifying name of the agent.
    status          "ok" | "warning" | "critical" — highest severity observed.
    risks           List of risk dicts (same shape as RiskAssessment output).
    recommendations List of recommendation dicts (same shape as
                    RecommendationEngine output, including ``confidence``).
    confidence      Overall agent confidence score (0.0 – 1.0), typically
                    the maximum confidence of its active recommendations.
    reasoning       One-paragraph natural-language summary of the agent's
                    reasoning for use in the explainable report.
    """
    agent: str
    status: str
    risks: list[RiskDict]
    recommendations: list[RecommendationDict]
    confidence: float
    reasoning: str
