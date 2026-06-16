# Implementation Plan: Phase 3A.5 Milestone 4.5 - Dynamic Threshold Integration

## 1. Objective
Refactor the live evaluation pipeline to natively consume dynamic thresholds resolved by `ThresholdEngine`. This integration establishes the foundation for epoch-aware evaluation, maintains strictly stateless mathematical execution, and natively supports future Replay and Shadow parameterization without divergence from production behavior.

## 2. ThresholdMap Contract & Consistency

### 2.1. Parameter Coverage & Key Constants
The `ThresholdMap` explicitly maps to the PostgreSQL `dynamic_thresholds` schema, serving as the single source of truth for all threshold resolutions. The map natively uses the following constants for its parameter identifiers:
- `PARAM_TEMPERATURE = "TEMPERATURE"`
- `PARAM_HUMIDITY = "HUMIDITY"`
- `PARAM_EC = "EC"`
- `PARAM_PH = "PH"`
- `PARAM_VPD = "VPD"`
- `PARAM_PHYTOPHTHORA = "PHYTOPHTHORA"`

Legacy properties (e.g., `optimal_high`, `moisture_warn`) will be strictly normalized inside `ThresholdEngine` to the unified keys:
`optimal_min`, `optimal_max`, `warn_min`, `warn_max`, `critical_min`, `critical_max`.

### 2.2. TypedDict ThresholdBounds
To prevent silent key mismatches and typos within the assessors, the inner dictionary will be formally typed using a `TypedDict`:

```python
class ThresholdBounds(TypedDict, total=False):
    optimal_min: Optional[float]
    optimal_max: Optional[float]
    warn_min: Optional[float]
    warn_max: Optional[float]
    critical_min: Optional[float]
    critical_max: Optional[float]
    
ThresholdMap = Dict[str, ThresholdBounds]
```
Assessors will type-hint `thresholds: Optional[ThresholdMap]` enabling `mypy` to statically enforce key compliance.

### 2.3. Merge Algorithm
`ThresholdEngine.get_all_thresholds(epoch_id)` will:
1. Initialize the dict with static defaults from `_thresholds.py` (normalizing keys).
2. Fetch DB overrides for the given epoch.
3. Overwrite only the specific parameters containing dynamic rows, cleanly passing partial configurations (e.g., custom TEMPERATURE, default HUMIDITY) to the assessors.

---

## 3. Execution Pathways & Architectural Parity

### 3.1. Production vs Replay Parity Guarantees
Because `epoch_id` resolution is restricted entirely to the I/O layer, Replay and Production are mathematically identical:

**Production Path:**
```text
Gateway -> evaluate_orchestrated_async(epoch_id=None)
  → EpochManager.get_active_epoch() resolves Pointer (e.g., 7)
  → ThresholdEngine.get_all_thresholds(epoch_id=7) -> ThresholdMap
```
**Replay Path:**
```text
Replay Engine -> evaluate_orchestrated_async(epoch_id=7)
  → Skips EpochManager (explicit parameter)
  → ThresholdEngine.get_all_thresholds(epoch_id=7) -> ThresholdMap
```
**Converged Execution & Full Propagation:** Both paths inject the identical `ThresholdMap` into the exact same synchronous call stack, explicitly propagating the dictionary down to the deepest assessor logic:
```text
evaluate_orchestrated_async(reading, epoch_id)
└── evaluate_orchestrated(reading, thresholds=ThresholdMap)
    └── OrchardOrchestrator.run(snapshot, memory, thresholds=ThresholdMap)
        ├── WaterAgent.analyze(snapshot, thresholds=ThresholdMap)
        │   └── [Internal Math Assessor Logic Reads ThresholdMap]
        ├── DiseaseAgent.analyze(snapshot, thresholds=ThresholdMap)
        │   └── [Internal Math Assessor Logic Reads ThresholdMap]
        ├── NutritionAgent.analyze(snapshot, thresholds=ThresholdMap)
        │   └── [Internal Math Assessor Logic Reads ThresholdMap]
        └── FloweringAgent.analyze(snapshot, thresholds=ThresholdMap)
            └── [Internal Math Assessor Logic Reads ThresholdMap]
```

### 3.2. Execution Consistency Guarantee & EpochManager Consistency Model
**Point-in-Time Evaluation Isolation (Read Committed):**
The `active_epoch_pointer` resolution and ThresholdMap creation are executed atomically *before* the synchronous math pipeline begins. If the global epoch pointer changes from 7 to 8 during execution, concurrent evaluations remain isolated. Evaluation A completes against Epoch 7 bounds, and Evaluation B completes against Epoch 8 bounds. The exact threshold map used is locked at the precise millisecond the I/O barrier is crossed, guaranteeing no cross-contamination or race conditions. This will be formally documented in the `evaluate_async` docstrings.

---

## 4. Files to Modify

**`src/orchard_brain/engine.py`**
- Add `evaluate_async()` and `evaluate_orchestrated_async()` facades mapping the Execution Consistency Guarantee.
- Update synchronous evaluate methods to accept `thresholds`.

**`src/orchard_brain/health.py`, `risk.py`, `recommendation.py`**
- Update `.assess()` and `.recommend()` signatures.
- Replace direct `_thresholds` imports with explicit `TypedDict` getters.

**`src/orchard_brain/orchard_orchestrator.py` & `agents/*.py`**
- Cascade `thresholds` dictionary into `analyze()` methods.

**`src/orchard_brain/knowledge/threshold_engine.py`**
- Introduce `get_all_thresholds(epoch_id)` implementing the TypedDict normalization and partial-merge algorithm.

**`tests/test_dynamic_thresholds.py`**
- Implement dynamic mutation tests.

---

## 5. Acceptance Criteria
- [ ] `ThresholdMap` explicitly normalizes keys into `ThresholdBounds` (`TypedDict`).
- [ ] Production leverages `active_epoch_pointer` automatically when `epoch_id=None`.
- [ ] Replay bypasses pointer transparently via explicit `epoch_id=7` parameterization.
- [ ] Point-in-Time Evaluation Isolation prevents concurrent execution race conditions.
- [ ] All 6 parameters (`TEMPERATURE`, `HUMIDITY`, `EC`, `PH`, `VPD`, `PHYTOPHTHORA`) are natively supported and merged.
- [ ] Existing 255 tests continue to pass without modification.

---

## 6. Test Strategy
The existing 255 tests only validate the static fallback. To validate dynamic integration:

1. **Dynamic Mutation Proof:** 
   - Inject a mock `ThresholdMap` artificially lowering the critical temperature maximum.
   - Execute `evaluate_raw(..., thresholds=mock_map)`.
   - Assert the output explicitly triggers a heat risk. 
   *(Note: This test will natively fail if the TypedDict keys are misspelled, as `.get()` will miss and math will evaluate against static fallbacks).*
2. **Partial Merge Validation:** 
   - Test `ThresholdEngine.get_all_thresholds()` with a database containing only one row (e.g., `TEMPERATURE`).
   - Assert the output dictionary correctly contains the dynamic `TEMPERATURE` alongside the static `HUMIDITY` defaults.
3. **Fallback Parity Proof:** 
   - Execute `evaluate_raw(..., thresholds=None)`.
   - Assert the output matches identical inputs run against the legacy engine, proving legacy behavior remains 100% untouched.
4. **Epoch Resolution Parity Test:**
   - **Given:** The database `active_epoch_pointer` is set to `7`.
   - **Assert:** The output of `Production(epoch_id=None)` evaluates to strictly `==` the output of `Replay(epoch_id=7)` for identical telemetry input, mathematically proving complete behavioral convergence across resolution pathways.


# Phase 3A.5 Milestone 5: Replay Engine

## Overview
Phase 3A.5 Milestone 5 introduces the Replay Engine. It securely evaluates historical telemetry against specified `epoch_id` parameters without touching the hardware actuator layer or modifying the core `engine.py` pipeline.

> [!IMPORTANT]
> The engine is strictly bounded to data-processing. It bypasses `CommandDispatcher` entirely, mathematically proving that actuator emission is impossible.

## Architecture

### 1. Database & Models
`database/models.py` has been updated with explicit schemas:
- **`ReplayJobModel`**: Tracks job states, target epochs, and timeframe parameters.
- **`ReplayResultModel`**:
  - Contains explicit scalar columns for high-level metrics (`health_score`, `water_stress`, `nutrient_stress`) to enable rapid anomaly discovery.
  - Utilizes PostgreSQL `JSONB` for `evaluation_payload`, allowing complex variable-length arrays (e.g., specific risk triggers) to remain deeply queryable and natively diffable at the database level.

### 2. Repositories
`database/replay_repository.py` has been implemented to handle job and result persistence natively in PostgreSQL.

### 3. Replay Engine
The `ReplayEngine` in `src/orchard_brain/knowledge/replay_engine.py` is fully implemented:
1. Validates `FF_REPLAY_ENGINE`.
2. Evaluates telemetry using purely explicit arguments (no hidden runtime `ContextVar`).
3. Instantiates `OrchardBrain()` in a stateless manner.
4. Directly invokes `.evaluate_raw()` and writes the output dictionary to the database. 

### 4. API
The new endpoints are exposed in `api/routers/replay.py`:
- `POST /replay/jobs`
- `GET /replay/jobs/{job_id}`
- `GET /replay/jobs/{job_id}/results`

These endpoints are strictly gated by the `FF_REPLAY_ENGINE` feature flag (default `False`).

## Code Verification
- `engine.py` was structurally preserved without modification.
- `FF_REPLAY_ENGINE` is configured to `False`.
- Actuator pathways are physically isolated from the call chain.
