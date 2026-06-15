"""Phase 6 — Explainable AI Report.

Converts an ``OrchestratorResult`` into a structured, human-readable text
report for the orchard operator.  Every section is labelled and cited so
the farmer knows exactly why each recommendation was generated.

Output sections:
  1. Overall Status Banner
  2. Current Reading Summary
  3. Health Metrics (from existing HealthAssessment)
  4. Detected Trends
  5. Knowledge Graph Explanations
  6. Agent Findings (one paragraph per agent)
  7. Causal Reasoning Chains
  8. Prioritised Action Plan
  9. Confidence Summary
"""
from __future__ import annotations

from datetime import UTC, datetime

from ._agent_base import RecommendationDict
from .health import HealthResult
from .orchard_orchestrator import OrchestratorResult

_SEP = "─" * 65
_THICK = "═" * 65


def _now() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")


class OrchardReport:
    """Generate a human-readable explainable intelligence report.

    The report is a plain-text string.  To write it to file::

        report = OrchardReport()
        text = report.generate(result, health_result)
        with open("orchard_report.txt", "w") as f:
            f.write(text)
    """

    _STATUS_BANNER = {
        "ok":       "✓  STATUS: ALL SYSTEMS NOMINAL",
        "warning":  "⚠  STATUS: WARNINGS DETECTED — ATTENTION REQUIRED",
        "critical": "✗  STATUS: CRITICAL ISSUES — IMMEDIATE ACTION REQUIRED",
    }

    def generate(
        self,
        result: OrchestratorResult,
        health_result: HealthResult | None = None,   # optional for backward compat
    ) -> str:
        """Return the full report as a string."""
        lines: list[str] = []

        lines += self._header(result)
        lines += self._reading_summary(result, health_result)
        lines += self._health_metrics(health_result)
        lines += self._trends_section(result)
        lines += self._knowledge_graph_section(result)
        lines += self._agent_findings(result)
        lines += self._causal_chains_section(result)
        lines += self._action_plan(result)
        lines += self._confidence_summary(result)
        lines += self._footer()

        return "\n".join(lines)

    # ──────────────────────────────────────────── sections

    def _header(self, result: OrchestratorResult) -> list[str]:
        status = result.overall_status
        banner = self._STATUS_BANNER.get(status, status.upper())
        return [
            _THICK,
            "  ORCHARD BRAIN — INTELLIGENCE REPORT",
            f"  Generated: {_now()}",
            _THICK,
            "",
            f"  {banner}",
            f"  Overall confidence: {result.overall_confidence:.0%}",
            "",
        ]

    def _reading_summary(
        self, result: OrchestratorResult, health_result: HealthResult | None
    ) -> list[str]:
        s = result.snapshot
        vpd = s.vpd if s.vpd is not None else 0.0
        proxy_note = "  [proxy: derived from air RH]" if s.soil_moisture_is_proxy else ""
        lines = [
            _SEP,
            "SECTION 1 — CURRENT READING",
            _SEP,
            f"  Timestamp       : {s.timestamp.strftime('%Y-%m-%d %H:%M UTC') if s.timestamp.tzinfo else s.timestamp.strftime('%Y-%m-%d %H:%M')}",
            f"  Temperature     : {s.temperature:.1f} °C     (optimal: 25–32 °C)",
            f"  Soil Moisture   : {s.soil_moisture:.1f} %    (optimal: 40–60 % VWC){proxy_note}",
            f"  Humidity        : {s.humidity:.1f} %",
            f"  EC              : {s.ec:.0f} µS/cm  (optimal: 150–300 µS/cm)",
            f"  pH              : {s.ph:.2f}         (optimal: 5.5–6.5)",
            f"  VPD             : {vpd:.2f} kPa     (comfortable: <2.0 kPa)",
            f"  Rainfall        : {s.rainfall:.1f} mm",
            "",
        ]
        return lines

    def _health_metrics(self, health_result: HealthResult | None) -> list[str]:
        if health_result is None:
            return []
        lines = [
            _SEP,
            "SECTION 2 — HEALTH METRICS",
            _SEP,
            f"  Health Score    : {health_result.health_score:>3}/100",
            f"  Water Stress    : {health_result.water_stress:>3}/100  (0 = no stress)",
            f"  Nutrient Stress : {health_result.nutrient_stress:>3}/100  (0 = no stress)",
            f"  Temperature Score: {health_result.temperature_score:>3}/100",
            f"  VPD             : {health_result.vpd_kpa:.3f} kPa",
            "",
        ]
        return lines

    def _trends_section(self, result: OrchestratorResult) -> list[str]:
        lines = [_SEP, "SECTION 3 — TREND ANALYSIS", _SEP]
        if not result.trends:
            lines += [
                "  No significant trends detected.",
                "  (Requires ≥3 snapshots in memory for trend analysis.)",
                "",
            ]
        else:
            for t in result.trends:
                lines.append(f"  [{t.confidence:.0%}] {t.trend.upper().replace('_', ' ')}")
                lines.append(f"    Direction : {t.direction.title()}")
                lines.append(f"    Magnitude : {t.magnitude}")
                lines.append(f"    Detail    : {t.description}")
                lines.append("")
        return lines

    def _knowledge_graph_section(self, result: OrchestratorResult) -> list[str]:
        lines = [_SEP, "SECTION 4 — KNOWLEDGE GRAPH EXPLANATIONS", _SEP]
        for label, path in result.knowledge_paths.items():
            if path:
                lines.append(f"  {label}")
                lines.append(f"    Path: {' → '.join(path)}")
            else:
                lines.append(f"  {label}")
                lines.append("    Path: (no connection found)")
            lines.append("")
        return lines

    def _agent_findings(self, result: OrchestratorResult) -> list[str]:
        lines = [_SEP, "SECTION 5 — SPECIALIST AGENT FINDINGS", _SEP]
        for a in result.agent_assessments:
            status_sym = {"ok": "✓", "warning": "⚠", "critical": "✗"}.get(a["status"], "?")
            lines.append(f"  {status_sym} {a['agent']}  [{a['confidence']:.0%} confidence]")
            lines.append(f"    Status : {a['status'].upper()}")
            lines.append(f"    Reasoning: {a['reasoning']}")
            if a["risks"]:
                lines.append("    Risks  :")
                for r in a["risks"]:
                    lines.append(f"      • [{r['severity'].upper()}] {r['risk']}: {r['message']}")
            lines.append("")
        return lines

    def _causal_chains_section(self, result: OrchestratorResult) -> list[str]:
        lines = [_SEP, "SECTION 6 — CAUSAL REASONING CHAINS", _SEP]
        if not result.causal_chains:
            lines += ["  No causal chains triggered.", ""]
        else:
            for i, c in enumerate(result.causal_chains[:8], 1):  # top 8
                lines.append(f"  Chain {i}  [{c.confidence:.0%} confidence]")
                lines.append(f"    CAUSE   : {c.cause}")
                lines.append(f"    IMPACT  : {c.impact}")
                lines.append(f"    RISK    : {c.risk}")
                lines.append(f"    ACTION  : {c.action}")
                lines.append("")
        return lines

    def _action_plan(self, result: OrchestratorResult) -> list[str]:
        lines = [_SEP, "SECTION 7 — PRIORITISED ACTION PLAN", _SEP]
        if not result.ranked_recommendations:
            lines += ["  No actions required — orchard is in excellent condition.", ""]
            return lines

        priority_groups: dict[str, list[RecommendationDict]] = {
            "critical": [], "high": [], "medium": [], "low": [],
        }
        for rec in result.ranked_recommendations:
            p = rec.get("priority", "low")
            if p in priority_groups:
                priority_groups[p].append(rec)

        for priority, recs in priority_groups.items():
            if not recs:
                continue
            label = {"critical": "🔴 CRITICAL", "high": "🟠 HIGH", "medium": "🟡 MEDIUM", "low": "🟢 LOW"}[priority]
            lines.append(f"  {label}")
            for rec in recs:
                lines.append(f"    [{rec.get('confidence', 0.0):.0%}] {rec['action']}")
                lines.append(f"           {rec.get('reason', '')}")
            lines.append("")
        return lines

    def _confidence_summary(self, result: OrchestratorResult) -> list[str]:
        lines = [_SEP, "SECTION 8 — CONFIDENCE SUMMARY", _SEP]
        for a in result.agent_assessments:
            bar = _confidence_bar(a["confidence"])
            lines.append(f"  {a['agent']:<28} {bar}  {a['confidence']:.0%}")
        lines.append("")
        overall_bar = _confidence_bar(result.overall_confidence)
        lines.append(f"  {'Overall Confidence':<28} {overall_bar}  {result.overall_confidence:.0%}")
        lines.append("")
        return lines

    def _footer(self) -> list[str]:
        return [
            _THICK,
            "  Orchard Brain — Pure rule-based explainable intelligence.",
            "  Thresholds: Haifa Guide, Ngoc et al. 2024, Eguchi et al. 2024,",
            "              Tang et al. 2024, Guest & Drenth 2004.",
            _THICK,
        ]


def _confidence_bar(conf: float, width: int = 20) -> str:
    filled = round(conf * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"
