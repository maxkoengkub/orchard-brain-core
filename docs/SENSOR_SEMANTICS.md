# Sensor Semantics & Agronomic Assumptions

This document is the canonical reference for what each sensor channel *means*
in Orchard Brain, which thresholds apply to it, and the known proxy/units
caveats. It is the output of the Phase 0 sensor-semantics audit.

## Channels

| Channel | Symbol | Unit | Drives | Thresholds |
|---------|--------|------|--------|------------|
| Air temperature | `temperature` | °C | health score, heat/cold risk, VPD, Phytophthora | `TEMPERATURE` |
| Soil moisture (root zone) | `soil_moisture` | % VWC | irrigation, drought/waterlogging, flowering dry-spell, Phytophthora, yield | `SOIL_MOISTURE` |
| Air relative humidity | `humidity` | % RH | VPD computation (and future air-RH scoring) | `RELATIVE_HUMIDITY` |
| Fertigation EC | `ec` | µS/cm | nutrient deficiency/toxicity | `EC` |
| Soil/water pH | `ph` | 0–14 | nutrient lock-out (acid/alkaline) | `PH` |
| Vapor Pressure Deficit | `vpd` | kPa | atmospheric water stress | `VPD` |
| Rainfall | `rainfall` | mm | dry-period detection | — |

All thresholds live in `src/orchard_brain/_thresholds.py` (single source of truth).

## The soil-moisture vs relative-humidity distinction (IMPORTANT)

`soil_moisture` (root-zone **volumetric water content**, VWC) and `humidity`
(**air relative humidity**) are *physically different quantities* and must not
be conflated:

- **Soil VWC** describes how much water is available to the roots. Durian
  optimum is ~40–60 % VWC; waterlogging >75 %; wilting <10 %. These bands live
  in `SOIL_MOISTURE`.
- **Air RH** describes atmospheric moisture around the canopy. Durian optimum is
  ~75–85 % RH; dry air (<60 %) raises VPD/transpiration; very humid air (>90 %)
  raises fungal-disease pressure. These bands live in `RELATIVE_HUMIDITY`.

### Historical conflation (resolved in Phase 0)

Originally, `SensorSnapshot.from_reading()` set `soil_moisture = reading.humidity`,
i.e. air RH was fed into the pipeline as if it were soil VWC, and a single
`HUMIDITY` threshold object (holding VWC values) was applied to both. This was a
correctness hazard.

**Resolution (backward-compatible):**

1. Thresholds are split into `SOIL_MOISTURE` (VWC) and `RELATIVE_HUMIDITY`
   (air RH). `HUMIDITY` remains as a **deprecated alias** of `SOIL_MOISTURE`
   so existing imports keep working.
2. `soil_moisture` is now a first-class channel. `SensorSnapshot.from_reading()`
   and `OrchardBrain.evaluate_orchestrated/evaluate_full(_raw)` accept an optional
   `soil_moisture` (measured VWC).
3. When no VWC value is supplied, air humidity is used as an **explicit proxy**:
   `SensorSnapshot.soil_moisture_is_proxy` is set `True`, a one-time runtime
   warning is emitted, and the report labels the value `[proxy: derived from air RH]`.

> Default behaviour is unchanged (proxy fallback), so all existing tests pass.
> Supplying a real `soil_moisture` value is the recommended path once a VWC
> probe is available.

`RELATIVE_HUMIDITY` bands are defined and documented but **not yet wired into
the health/risk/recommendation scoring**, to avoid changing current outputs.
Wiring true air-RH scoring is a follow-up (Phase 1+) and would be a deliberate
behaviour change.

## Units & assumptions to keep in mind

- **EC** is the **fertigation solution** EC in µS/cm (healthy ≈ 150–300 µS/cm).
  Agronomic literature often cites **soil bulk EC** in dS/m (1 dS/m = 1000 µS/cm).
  Do not compare the two directly.
- **pH** thresholds target **soil** pH (5.5–6.5 optimal). Irrigation-water pH
  targets differ (≈ 6.0–7.5) and are not separately modelled.
- **VPD** is derived from `temperature` + air `humidity` via the Magnus/Tetens
  approximation (`compute_vpd_kpa`). It requires *air RH*, which is supplied
  correctly even when `soil_moisture` is a proxy.
- **Rainfall** defaults to `0.0` when no rain gauge is installed; dry-period
  detection treats `< 0.1 mm` as effectively dry.

## Research basis

Thresholds are grounded in: Haifa Group Durian Guide (climate, RH, pH),
Ngoc et al. (2024) and Tang et al. (2024) (nutrients/EC), Eguchi et al. (2024)
(flowering dry-spell ~15 days), Guest & Drenth (2004) (Phytophthora), and
FAO/extension manuals (soil pH 5.5–6.5, VWC 40–60 %).
