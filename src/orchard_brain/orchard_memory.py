"""Phase 1 — Temporal Memory.

Stores time-ordered SensorSnapshots in memory and detects agronomic trends
across the stored window.

Usage::

    mem = OrchardMemory()
    mem.save_snapshot(SensorSnapshot(timestamp=datetime.now(), ...))
    trends = mem.detect_trends()
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ._thresholds import SOIL_MOISTURE, TEMPERATURE, VPD, compute_vpd_kpa

_soil_moisture_proxy_warned = False


def _warn_soil_moisture_proxy_once() -> None:
    """Emit a single process-wide warning when air RH is used as a VWC proxy.

    Air relative humidity and soil volumetric water content are physically
    different quantities; using one for the other is a known limitation until a
    dedicated VWC probe is installed.  The warning fires once to avoid log spam.
    """
    global _soil_moisture_proxy_warned
    if not _soil_moisture_proxy_warned:
        _soil_moisture_proxy_warned = True
        warnings.warn(
            "soil_moisture not supplied; using air humidity as a proxy. "
            "Provide a measured VWC value (SensorSnapshot.from_reading("
            "..., soil_moisture=...)) for accurate root-zone assessment.",
            stacklevel=3,
        )


# ─────────────────────────────────────────────────── data structures


@dataclass
class SensorSnapshot:
    """One point-in-time reading of all orchard sensor channels.

    Channel semantics (see docs/SENSOR_SEMANTICS.md):
      - ``soil_moisture`` is root-zone volumetric water content (VWC, %).  It is
        physically distinct from air ``humidity``.  When no VWC probe is yet
        deployed, air humidity may be supplied as an explicit *proxy*, in which
        case ``soil_moisture_is_proxy`` is True.
      - ``humidity`` is air relative humidity (%), used for VPD.
      - ``vpd`` is computed from temperature + humidity if not provided.
      - ``rainfall`` defaults to 0.0 if no rain gauge is installed.
    """
    timestamp: datetime
    soil_moisture: float        # % VWC (root zone); may be an air-RH proxy — see flag
    temperature: float          # °C
    humidity: float             # % air relative humidity (drives VPD)
    ph: float                   # soil/water pH
    ec: float                   # µS/cm fertigation solution EC
    rainfall: float = 0.0       # mm in this sampling period (0 if no gauge)
    vpd: float | None = None # kPa — auto-computed below if None
    soil_moisture_is_proxy: bool = False  # True when soil_moisture is derived from air RH

    def __post_init__(self) -> None:
        if self.vpd is None:
            self.vpd = compute_vpd_kpa(self.temperature, self.humidity)

    @classmethod
    def from_reading(
        cls,
        reading: object,
        rainfall: float = 0.0,
        soil_moisture: float | None = None,
    ) -> SensorSnapshot:
        """Construct from any object with .temperature, .humidity, .ec, .ph.

        Args:
            reading: Object exposing ``.temperature``, ``.humidity``, ``.ec``,
                     ``.ph`` (all floats).
            rainfall: Optional rainfall (mm) for this sampling period.
            soil_moisture: Measured root-zone VWC (%).  When ``None`` (no probe
                           available), air ``humidity`` is used as an explicit
                           proxy and ``soil_moisture_is_proxy`` is set True.

        The default (``soil_moisture=None``) preserves the original behaviour
        exactly, while making the proxy explicit and overridable.
        """
        if soil_moisture is None:
            soil_moisture_value = reading.humidity  # type: ignore[attr-defined]
            is_proxy = True
            _warn_soil_moisture_proxy_once()
        else:
            soil_moisture_value = soil_moisture
            is_proxy = False

        return cls(
            timestamp=datetime.now(tz=UTC),
            soil_moisture=soil_moisture_value,
            temperature=reading.temperature,  # type: ignore[attr-defined]
            humidity=reading.humidity,  # type: ignore[attr-defined]
            ph=reading.ph,  # type: ignore[attr-defined]
            ec=reading.ec,  # type: ignore[attr-defined]
            rainfall=rainfall,
            soil_moisture_is_proxy=is_proxy,
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
        cutoff = datetime.now(tz=UTC) - timedelta(days=days)
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

    def latest(self) -> SensorSnapshot | None:
        return self._snapshots[-1] if self._snapshots else None


# ─────────────────────────────────────────────────── trend detectors


def _utc(dt: datetime) -> datetime:
    """Ensure tz-aware UTC for comparison."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
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
                f"{'Drought warning active.' if vals[-1] < SOIL_MOISTURE.warn_low else ''}"
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
    dry_count = sum(1 for s in snaps if s.soil_moisture < SOIL_MOISTURE.warn_low and s.rainfall < 0.1)
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
                f"{SOIL_MOISTURE.warn_low:.0f} % with near-zero rainfall ({ratio:.0%} of window). "
                "Prolonged dry conditions may trigger durian flowering initiation "
                "if sustained for ~15 days (Eguchi et al., 2024)."
            ),
        )]
    return []


def _wet_period_trend(snaps: list[SensorSnapshot]) -> list[TrendResult]:
    """Detect excessive wet period (Phytophthora risk window)."""
    wet_count = sum(1 for s in snaps if s.soil_moisture > SOIL_MOISTURE.warn_high)
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
                f"{SOIL_MOISTURE.warn_high:.0f} % ({ratio:.0%} of window). "
                "Persistently wet soil significantly raises Phytophthora palmivora "
                "infection risk (Guest & Drenth, 2004)."
            ),
        )]
    return []
