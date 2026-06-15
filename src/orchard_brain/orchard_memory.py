"""Phase 1 — Temporal Memory.

Stores time-ordered SensorSnapshots in memory and detects agronomic trends
across the stored window.

Usage::

    mem = OrchardMemory()
    mem.save_snapshot(SensorSnapshot(timestamp=datetime.now(), ...))
    trends = mem.detect_trends()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from ._thresholds import HUMIDITY, TEMPERATURE, VPD, compute_vpd_kpa


# ─────────────────────────────────────────────────── data structures


@dataclass
class SensorSnapshot:
    """One point-in-time reading of all orchard sensor channels.

    ``rainfall`` and ``vpd`` can be derived if not directly measured:
      - ``vpd`` is computed from temperature + humidity if not provided.
      - ``rainfall`` defaults to 0.0 if no rain gauge is installed.
    """
    timestamp: datetime
    soil_moisture: float        # % (humidity proxy until VWC probe is installed)
    temperature: float          # °C
    humidity: float             # % relative humidity (same sensor as soil_moisture
                                #    for this system — see architecture note)
    ph: float                   # soil/water pH
    ec: float                   # µS/cm fertigation solution EC
    rainfall: float = 0.0       # mm in this sampling period (0 if no gauge)
    vpd: Optional[float] = None # kPa — auto-computed below if None

    def __post_init__(self) -> None:
        if self.vpd is None:
            self.vpd = compute_vpd_kpa(self.temperature, self.humidity)

    @classmethod
    def from_reading(cls, reading: object, rainfall: float = 0.0) -> "SensorSnapshot":
        """Construct from any object with .temperature, .humidity, .ec, .ph."""
        return cls(
            timestamp=datetime.now(tz=timezone.utc),
            soil_moisture=reading.humidity,
            temperature=reading.temperature,
            humidity=reading.humidity,
            ph=reading.ph,
            ec=reading.ec,
            rainfall=rainfall,
        )


@dataclass
class TrendResult:
    """A detected trend across the stored memory window."""
    trend: str           # identifier (see KNOWN_TRENDS below)
    direction: str       # "rising" | "falling" | "sustained"
    magnitude: float     # absolute change over the observation window
    confidence: float    # 0.0 – 1.0, based on number of samples and consistency
    description: str     # human-readable explanation with values


# Trend identifiers surfaced by detect_trends()
KNOWN_TRENDS = (
    "rising_temperature",
    "falling_soil_moisture",
    "increasing_vpd",
    "prolonged_dry_period",
    "excessive_wet_period",
)


# ─────────────────────────────────────────────────── memory store


class OrchardMemory:
    """In-process ring buffer of SensorSnapshots with trend detection.

    Thread-safety: not required (single-process, async-free pipeline).
    Persistence: snapshots are lost on restart — add a database writer in
    the main loop if persistence is required.
    """

    def __init__(self, max_snapshots: int = 2880) -> None:
        # 2880 = 24 h × 60 min / 30 s sampling × 2 — roughly 2 days at 30 s
        self._snapshots: list[SensorSnapshot] = []
        self._max = max_snapshots

    # ─────────────────────────────────────────────── public API

    def save_snapshot(self, snapshot: SensorSnapshot) -> None:
        """Append a snapshot, evicting the oldest if the ring is full."""
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self._max:
            self._snapshots.pop(0)

    def get_last_days(self, days: float) -> list[SensorSnapshot]:
        """Return snapshots from the last ``days`` days."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
        return [
            s for s in self._snapshots
            if _utc(s.timestamp) >= cutoff
        ]

    def get_recent_snapshots(self, limit: int) -> list[SensorSnapshot]:
        """Return the ``limit`` most recent snapshots (newest last)."""
        return self._snapshots[-limit:]

    def detect_trends(self) -> list[TrendResult]:
        """Analyse stored snapshots and return a list of active trends.

        Returns an empty list if fewer than 3 snapshots are stored
        (insufficient history for reliable trend analysis).
        """
        snaps = self._snapshots
        if len(snaps) < 3:
            return []

        trends: list[TrendResult] = []
        trends.extend(_temperature_trend(snaps))
        trends.extend(_soil_moisture_trend(snaps))
        trends.extend(_vpd_trend(snaps))
        trends.extend(_dry_period_trend(snaps))
        trends.extend(_wet_period_trend(snaps))
        return trends

    # ─────────────────────────────────────────────── read-only helpers

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)

    def latest(self) -> Optional[SensorSnapshot]:
        return self._snapshots[-1] if self._snapshots else None


# ─────────────────────────────────────────────────── trend detectors


def _utc(dt: datetime) -> datetime:
    """Ensure tz-aware UTC for comparison."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _linear_slope(values: list[float]) -> float:
    """Least-squares slope (units per sample)."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den > 0 else 0.0


def _confidence_from_sample_count(n: int) -> float:
    """More samples → higher confidence (asymptotic to 0.95)."""
    return min(0.95, 0.50 + n * 0.01)


def _temperature_trend(snaps: list[SensorSnapshot]) -> list[TrendResult]:
    vals = [s.temperature for s in snaps]
    slope = _linear_slope(vals)
    delta = vals[-1] - vals[0]
    if abs(delta) < 1.0:
        return []
    if slope > 0:
        conf = min(0.90, _confidence_from_sample_count(len(snaps)) + abs(slope) * 0.05)
        return [TrendResult(
            trend="rising_temperature",
            direction="rising",
            magnitude=round(delta, 2),
            confidence=round(conf, 2),
            description=(
                f"Temperature has risen {delta:+.1f} °C over the last "
                f"{len(snaps)} samples "
                f"(current: {vals[-1]:.1f} °C, slope: {slope:+.3f} °C/sample). "
                f"{'Heat stress risk is building.' if vals[-1] >= TEMPERATURE.warn_high else ''}"
            ),
        )]
    return []


def _soil_moisture_trend(snaps: list[SensorSnapshot]) -> list[TrendResult]:
    vals = [s.soil_moisture for s in snaps]
    slope = _linear_slope(vals)
    delta = vals[-1] - vals[0]
    if delta < -3.0:  # at least 3 % drop
        conf = min(0.90, _confidence_from_sample_count(len(snaps)) + abs(slope) * 0.05)
        return [TrendResult(
            trend="falling_soil_moisture",
            direction="falling",
            magnitude=round(abs(delta), 2),
            confidence=round(conf, 2),
            description=(
                f"Soil moisture has fallen {delta:.1f} % over the last "
                f"{len(snaps)} samples "
                f"(current: {vals[-1]:.1f} %, slope: {slope:+.3f} %/sample). "
                f"{'Drought warning active.' if vals[-1] < HUMIDITY.warn_low else ''}"
            ),
        )]
    return []


def _vpd_trend(snaps: list[SensorSnapshot]) -> list[TrendResult]:
    vals = [s.vpd for s in snaps if s.vpd is not None]
    if len(vals) < 3:
        return []
    slope = _linear_slope(vals)
    delta = vals[-1] - vals[0]
    if slope > 0 and delta > 0.3:  # meaningful VPD increase
        conf = min(0.90, _confidence_from_sample_count(len(snaps)) + slope * 0.1)
        return [TrendResult(
            trend="increasing_vpd",
            direction="rising",
            magnitude=round(delta, 3),
            confidence=round(conf, 2),
            description=(
                f"Vapor Pressure Deficit has increased {delta:+.2f} kPa over "
                f"the last {len(snaps)} samples "
                f"(current: {vals[-1]:.2f} kPa). "
                f"{'VPD stress threshold exceeded.' if vals[-1] >= VPD.warn_high else 'Evaporative demand is rising.'}"
            ),
        )]
    return []


def _dry_period_trend(snaps: list[SensorSnapshot]) -> list[TrendResult]:
    """Detect a prolonged dry period based on soil moisture and rainfall.

    Criterion (research — Eguchi et al. 2024): sustained low moisture
    (below warn_low) over multiple consecutive samples signals a dry spell
    that may trigger flowering initiation.
    """
    dry_count = sum(1 for s in snaps if s.soil_moisture < HUMIDITY.warn_low and s.rainfall < 0.1)
    ratio = dry_count / len(snaps)
    if ratio >= 0.6 and len(snaps) >= 6:
        conf = min(0.90, 0.55 + ratio * 0.35)
        return [TrendResult(
            trend="prolonged_dry_period",
            direction="sustained",
            magnitude=round(ratio * 100, 1),
            confidence=round(conf, 2),
            description=(
                f"{dry_count}/{len(snaps)} samples show soil moisture below "
                f"{HUMIDITY.warn_low:.0f} % with near-zero rainfall ({ratio:.0%} of window). "
                "Prolonged dry conditions may trigger durian flowering initiation "
                "if sustained for ~15 days (Eguchi et al., 2024)."
            ),
        )]
    return []


def _wet_period_trend(snaps: list[SensorSnapshot]) -> list[TrendResult]:
    """Detect excessive wet period (Phytophthora risk window)."""
    wet_count = sum(1 for s in snaps if s.soil_moisture > HUMIDITY.warn_high)
    ratio = wet_count / len(snaps)
    if ratio >= 0.5 and len(snaps) >= 6:
        conf = min(0.90, 0.55 + ratio * 0.35)
        return [TrendResult(
            trend="excessive_wet_period",
            direction="sustained",
            magnitude=round(ratio * 100, 1),
            confidence=round(conf, 2),
            description=(
                f"{wet_count}/{len(snaps)} samples show soil moisture above "
                f"{HUMIDITY.warn_high:.0f} % ({ratio:.0%} of window). "
                "Persistently wet soil significantly raises Phytophthora palmivora "
                "infection risk (Guest & Drenth, 2004)."
            ),
        )]
    return []
