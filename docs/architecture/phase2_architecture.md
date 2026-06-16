# Phase 2D: Orchard Brain Integration — Revised Implementation Plan

This document details the architecture and implementation strategy for integrating the deterministic, rule-based agronomic intelligence of `OrchardBrain` into the Gateway Service pipeline. It incorporates all three fixes identified in the architecture review.

## Goal Description

When a `DATA_UPLINK` LoRa packet arrives at the gateway, the service will:
1. Decode the packet into a `SensorReading`.
2. Enqueue it into an internal async buffer.
3. A processing coroutine will dequeue it, persist the raw reading, run the deterministic `OrchardBrain.evaluate()`, and persist the resulting health scores, risks, and recommendations.
4. The Phase 2B API endpoints (`GET /recommendations`, `GET /risk-summary`, `GET /sensor-history`) serve the persisted results unchanged.

## Excluded Scope

Per requirements, the following will **NOT** be implemented:
- Machine learning
- Temporal memory (`enable_memory=False`)
- Knowledge ingestion pipeline
- Causal engine / LLM reasoning (`evaluate_full()` and `evaluate_orchestrated()` will not be called)

---

## Fix #1: Decouple `_on_receive` from Processing via `asyncio.Queue`

### Problem
`_on_receive()` is a synchronous callback invoked by the UART transport thread. Embedding database writes and brain evaluation inside it violates the async/sync boundary and risks blocking the radio I/O path.

### Solution
Introduce an `asyncio.Queue` as an intermediate buffer inside `GatewayService`:

```
_on_receive()         asyncio.Queue         _process_readings()
  (sync, UART)    →    (in-memory)     →    (async coroutine)
  decode frame          enqueue              dequeue
  correlate ACKs        (node_id,            save_sensor_reading()
                         reading)            brain.evaluate()
                                             save_brain_result()
```

#### [MODIFY] gateway/service.py
- Add `self._reading_queue: asyncio.Queue` to `__init__`.
- In `_on_receive()`, when a `PKT_TYPE_DATA_UPLINK` is decoded, call `self._reading_queue.put_nowait((node_id, reading))` instead of performing any async work.
- ACK correlation for inflight commands remains in `_on_receive()` as-is (it is a pure dict lookup, no async needed).
- Add a new `_process_readings()` coroutine started alongside `_poll_loop()` and `_timeout_loop()` in `start()`. This coroutine loops on `await self._reading_queue.get()`, performs the DB writes and brain evaluation.

---

## Fix #2: Session Factory Instead of Long-Lived Session

### Problem
A single `AsyncSession` shared across the entire service lifetime accumulates stale objects and breaks on any failed transaction, blocking all subsequent operations.

### Solution
Inject an `async_sessionmaker` into `GatewayService` instead of a pre-built `DatabaseRepository`. Create a fresh session and repository per processing cycle.

#### [MODIFY] gateway/service.py
- Change the constructor signature from `repository: DatabaseRepository` to `session_factory: async_sessionmaker`.
- In `_poll_loop()`, create a fresh session per cycle:
  ```python
  async with self.session_factory() as session:
      repo = DatabaseRepository(session)
      pending_cmds = await repo.get_pending_commands(...)
      ...
  ```
- In `_process_readings()`, create a fresh session per reading:
  ```python
  async with self.session_factory() as session:
      repo = DatabaseRepository(session)
      await repo.save_sensor_reading(reading)
      brain_result = await asyncio.to_thread(self.brain.evaluate, reading)
      await repo.save_brain_result(node_id, dt, brain_result)
  ```
- In `_on_receive()` ACK handling, schedule a small coroutine that opens its own session to update command status.

#### [MODIFY] gateway/main.py
- Pass the `async_sessionmaker` instance to `GatewayService` instead of a pre-built session/repo.

#### [MODIFY] gateway/tests/test_service.py
- Update fixtures to provide an `async_sessionmaker` instead of a raw session.

---

## Fix #3: `BrainResult` → Database Key Mapping

### Problem
`save_orchestrator_result()` expects `risk["type"]` and `risk["description"]`, but `OrchardBrain.evaluate()` returns `Risk` TypedDicts with keys `risk["risk"]` and `risk["message"]`. This will crash with a `KeyError` at runtime.

### Solution
Create a dedicated `save_brain_result()` method in `DatabaseRepository` that correctly maps the `BrainResult` TypedDict keys to the database model columns.

#### [MODIFY] database/repository.py
- Add a new method `save_brain_result(node_id, dt, brain_result)` that:
  - Creates `OrchardHealthModel` from `brain_result["health_score"]`, `brain_result["water_stress"]`, `brain_result["nutrient_stress"]`.
  - Iterates `brain_result["risks"]` using the correct keys: `risk["risk"]` → `risk_type`, `risk["severity"]` → `severity`, `risk["message"]` → `description`.
  - Iterates `brain_result["recommendations"]` using: `rec["action"]`, `rec["priority"]`, `rec["reason"]`, `rec["confidence"]`.
- The existing `save_orchestrator_result()` is left untouched for backward compatibility with any future `OrchestratorResult` consumers.

---

## Additional Changes

### Brain Injection

#### [MODIFY] gateway/service.py
- Add `brain: OrchardBrain` as a constructor parameter.
- Instantiate with `OrchardBrain(enable_memory=False)` in `gateway/main.py` for strictly deterministic, stateless evaluation.

### Uplink Handling in `_on_receive`

#### [MODIFY] gateway/service.py
- Import `PKT_TYPE_DATA_UPLINK` from the decoder constants.
- In `_on_receive()`, add a branch for `PKT_TYPE_DATA_UPLINK`:
  ```
  if pkt_type == PKT_TYPE_DATA_UPLINK:
      self._reading_queue.put_nowait((src_node_id, decoded_reading))
  ```

---

## Directory Structure

No new files are created. All changes are modifications to existing files:

```text
database/
└── repository.py          # Add save_brain_result()

gateway/
├── service.py             # Add Queue, _process_readings(), session factory, brain injection
├── main.py                # Update to pass session_factory + OrchardBrain
└── tests/
    └── test_service.py    # Update fixtures, add uplink integration test
```

---

## File Change Summary

| File | Change | Reason |
|---|---|---|
| [repository.py](file:///c:/Users/zonob/orchard-brain-core/database/repository.py) | Add `save_brain_result()` | Fix #3: correct key mapping |
| [service.py](file:///c:/Users/zonob/orchard-brain-core/gateway/service.py) | Add `asyncio.Queue`, `_process_readings()`, accept `session_factory` + `brain` | Fix #1 + Fix #2 + brain integration |
| [main.py](file:///c:/Users/zonob/orchard-brain-core/gateway/main.py) | Pass `async_sessionmaker` and `OrchardBrain` instance | Fix #2 + brain integration |
| [test_service.py](file:///c:/Users/zonob/orchard-brain-core/gateway/tests/test_service.py) | Update fixtures, add uplink→brain→DB integration test | Verify all three fixes |

---

## Test Strategy

### Unit Tests
- Verify that `save_brain_result()` correctly maps `Risk` keys (`risk`, `severity`, `message`) to DB columns (`risk_type`, `severity`, `description`).
- Verify that `_on_receive()` enqueues uplink readings into the queue without blocking.
- Verify that `_process_readings()` dequeues, evaluates, and persists correctly.

### Integration Tests
- Simulate a full `DATA_UPLINK` frame arriving via `MockTransport`.
- Assert that `SensorReadingModel` is written to the database.
- Assert that `OrchardHealthModel` is written with a valid health score.
- Assert that `RiskModel` entries are created when sensor values exceed thresholds.
- Assert that `RecommendationModel` entries are created with correct action keys.
- Verify that session isolation works: a failed evaluation for one reading does not corrupt the next.

### Regression
- Run `python -m pytest database/tests/` — Phase 2A tests must pass.
- Run `python -m pytest api/tests/` — Phase 2B tests must pass.
- Run `python -m pytest gateway/tests/` — Phase 2C + 2D tests must pass.

---

## Verification Plan

### Automated Tests
```bash
python -m pytest database/tests/ gateway/tests/ api/tests/ -v
```

### Manual Verification
- Instantiate `GatewayService` with `MockTransport` and in-memory SQLite.
- Inject a crafted uplink packet with temperature = 40.0 °C (above critical threshold).
- Verify that the database contains a `heat_stress` risk with severity `critical` and a `trigger_micro_sprinkler_cooling` recommendation with priority `critical`.


# Phase 2D Architecture Review

**Reviewer Role:** Principal AI Architect, Agronomist, Systems Engineer  
**Date:** 2026-06-15  
**Scope:** Review of the proposed Orchard Brain integration into the Gateway Service pipeline.

---

## 1. Architecture Correctness

### 1.1 Pipeline Flow — Correct

The proposed pipeline is sound:

```
LoRa Packet → _on_receive() → LoRaDecoder → SensorReading
                                                  ↓
                                          save_sensor_reading()
                                                  ↓
                                     OrchardBrain.evaluate()
                                                  ↓
                                     save_orchestrator_result()
                                                  ↓
                              API serves via GET /recommendations, /risk-summary
```

This is the correct topology for a deterministic, single-pass evaluation. The data flows linearly, and there are no circular dependencies.

### 1.2 Placement of Brain Evaluation — Design Flaw Identified

> [!WARNING]
> **FLAW #1: Brain evaluation is embedded inside `_on_receive()`, which is a synchronous transport callback.**
>
> The `_on_receive` method in [service.py](file:///c:/Users/zonob/orchard-brain-core/gateway/service.py#L53-L74) is invoked by the `TransportInterface` — which, in the production `LoraSerial` implementation, fires from a UART reader thread. This callback currently:
> 1. Decodes the frame (fast, microseconds)
> 2. Correlates ACKs for inflight commands (fast, dict lookup)
>
> The plan proposes adding to this callback:
> 3. Database write (`save_sensor_reading` — async, requires event loop)
> 4. Brain evaluation (`OrchardBrain.evaluate()` — synchronous, CPU-bound ~1-5ms)
> 5. Database write (`save_orchestrator_result` — async, requires event loop)
>
> **Problem:** Steps 3-5 require `async` context but `_on_receive` is a synchronous callback. The current code uses `asyncio.get_event_loop().create_task()` for the ACK update, which is fragile — it assumes the callback runs on the same thread as the event loop. For brain evaluation + DB writes, this becomes untenable.

**Recommendation:** Decouple the receive callback from the processing pipeline. The callback should only enqueue decoded payloads into an `asyncio.Queue`. A separate `_process_readings()` coroutine should consume from that queue, run the brain evaluation, and persist results. This gives clean async/sync separation.

```
_on_receive()  →  asyncio.Queue  →  _process_readings() coroutine
   (sync,             (buffer)          (async, runs brain + DB)
    UART thread)
```

### 1.3 Session Lifecycle — Design Flaw Identified

> [!WARNING]
> **FLAW #2: Single `DatabaseRepository` session shared across the entire service lifetime.**
>
> The `GatewayService` receives a single `DatabaseRepository` (wrapping a single `AsyncSession`) in its constructor. This session is used for:
> - Command polling (every 1 second)
> - Command status updates
> - Sensor reading persistence (every incoming uplink)
> - Brain result persistence
>
> A long-lived session accumulates stale objects in its identity map, and any single failed transaction will leave the session in a broken state, blocking all subsequent operations.

**Recommendation:** Use a session factory (`async_sessionmaker`) instead of a pre-built session. Create a fresh session per processing cycle or per incoming reading. This is the standard pattern for long-running services.

### 1.4 `save_orchestrator_result` Contract Mismatch — Design Flaw Identified

> [!CAUTION]
> **FLAW #3: The `save_orchestrator_result` method expects `risk["type"]` and `risk["description"]`, but `OrchardBrain.evaluate()` returns `risk["risk"]` and `risk["message"]`.**
>
> The `BrainResult` from [engine.py](file:///c:/Users/zonob/orchard-brain-core/src/orchard_brain/engine.py#L58-L64) contains a `risks` list of `Risk` TypedDicts with keys `risk`, `severity`, `message`. But `save_orchestrator_result` in [repository.py](file:///c:/Users/zonob/orchard-brain-core/database/repository.py#L77-L85) reads `risk["type"]` and `risk["description"]` — keys that do not exist.
>
> **This will crash at runtime with a `KeyError`.**

**Recommendation:** Add a translation layer between the `BrainResult` output and the repository input. Either:
- (A) Fix `save_orchestrator_result` to use the correct keys (`risk["risk"]`, `risk["message"]`), or
- (B) Create a dedicated `save_brain_result(node_id, dt, brain_result: BrainResult)` method that maps the TypedDict fields correctly.

Option (B) is cleaner because it documents the contract explicitly.

---

## 2. Agronomic Correctness

### 2.1 Threshold Coverage — Correct and Research-Grounded

The rule engine in [_thresholds.py](file:///c:/Users/zonob/orchard-brain-core/src/orchard_brain/_thresholds.py) is agronomically sound for durian (*Durio zibethinus*):

| Parameter | Optimal Range | Research Basis | Verdict |
|---|---|---|---|
| Temperature | 25–32 °C | Haifa Guide | ✅ Correct |
| Soil Moisture (VWC proxy) | 40–60 % | FAO/Haifa | ✅ Correct |
| EC (fertigation) | 150–300 µS/cm | Tang et al. (2024) | ✅ Correct |
| pH | 5.5–6.5 | Ngoc et al. (2024) / FAO | ✅ Correct |
| VPD | < 2.0 kPa comfortable | Tropical durian context | ✅ Reasonable |
| Phytophthora | 25–35 °C × >70% moisture | Guest & Drenth (2004) | ✅ Correct |

### 2.2 Disease Risk Model — Adequate for Phase 2D

The Phytophthora model uses temperature × moisture as a proxy. This is valid for a deterministic rule engine. The model correctly identifies:
- Warning at 70% moisture in the 25–35 °C window
- Critical at 80% moisture in the same window

### 2.3 Missing Agronomic Signal — Technical Debt

> [!NOTE]
> **DEBT #1: `soil_moisture` field exists in `SensorReading` but `OrchardBrain.evaluate()` only accepts `temperature`, `humidity`, `ec`, `ph`.**
>
> The `evaluate()` method in [engine.py L87-102](file:///c:/Users/zonob/orchard-brain-core/src/orchard_brain/engine.py#L87-L102) extracts only 4 fields: `reading.temperature`, `reading.humidity`, `reading.ec`, `reading.ph`. It does **not** pass `soil_moisture` or `rainfall` to the assessors.
>
> The `humidity` field is used as a soil moisture proxy (documented in `_thresholds.py` line 40-41), but the ESP32 firmware transmits actual `soil_moisture` from the capacitive VWC sensor alongside `humidity` from the SHT40. These are two different measurements.

**Recommendation (future phase):** When the brain is extended, pass `soil_moisture` as the primary VWC input and reserve `humidity` for atmospheric RH. This will require updating `HealthAssessment`, `RiskAssessment`, and `RecommendationEngine` to accept a 5th or 6th parameter. For Phase 2D, document this as known technical debt but do not change the brain interface.

### 2.4 Rainfall Not Used — Technical Debt

> [!NOTE]
> **DEBT #2: `rainfall` data arrives from nodes but is never consumed by the brain evaluation.**
>
> The `SensorReading` model includes `rainfall: Optional[float]`, and the ESP32 transmits accumulated rainfall per cycle. However, `OrchardBrain.evaluate()` ignores it entirely. Rainfall is critical for:
> - Phytophthora risk scoring (wet canopy + warm soil)
> - Irrigation scheduling (subtracting natural precipitation)
> - Flowering trigger detection (Eguchi et al., 2024: 15-day dry spell)

**Recommendation (future phase):** This is acceptable for Phase 2D since we are not modifying the brain interface. Flag as technical debt.

---

## 3. Scalability

### 3.1 Current Load Profile — Adequate

With the Phase 1 specification:
- 64 nodes max per gateway
- 5-minute transmit intervals
- 1 reading per node per cycle

This produces **~12.8 readings per minute** at maximum deployment. `OrchardBrain.evaluate()` is pure Python arithmetic taking <5ms per call. Total CPU load for brain evaluation: **~64 ms/minute** — negligible.

### 3.2 Database Write Amplification — Monitor

Each incoming sensor reading produces:
1. 1 × `SensorReadingModel` INSERT
2. 1 × `OrchardHealthModel` INSERT
3. 0–N × `RiskModel` INSERTs (typically 0–4 per reading)
4. 0–N × `RecommendationModel` INSERTs (typically 1–6 per reading)

Worst case per reading: **~12 INSERTs**. At 64 nodes: **~768 INSERTs per 5-minute window** (~2.5/sec). This is well within PostgreSQL/TimescaleDB capacity, but all writes currently happen inside a single `await session.commit()` call in `save_orchestrator_result`, which is efficient.

### 3.3 No Backpressure Mechanism — Technical Debt

> [!NOTE]
> **DEBT #3: If the database or brain evaluation stalls, there is no mechanism to apply backpressure to the radio receive path.**
>
> If the `_on_receive` callback (or any future processing coroutine) falls behind, decoded readings are simply lost because there is no intermediate queue with durability.

**Recommendation:** The `asyncio.Queue` proposed in §1.2 provides in-memory backpressure. For durability, the Phase 1 architecture already specified an `ingestion_queue` (SQLite WAL) — consider implementing this as a future hardening step.

---

## 4. Concurrency Model

### 4.1 `asyncio.to_thread()` — Acceptable but Unnecessary

The plan proposes running `OrchardBrain.evaluate()` inside `asyncio.to_thread()` to avoid blocking the event loop. This is technically correct, but:

- `evaluate()` takes <5ms (pure arithmetic, no I/O)
- At 64 nodes / 5 min, calls arrive ~once every 4.7 seconds
- The event loop tick budget is typically 50–100ms before responsiveness degrades

**Verdict:** Using `asyncio.to_thread()` is harmless but adds unnecessary thread-pool overhead for a <5ms computation. A direct `await`-wrapped call or even a synchronous call within the async context would be acceptable at this scale.

**Recommendation:** Use `asyncio.to_thread()` anyway. The overhead is negligible, and it future-proofs the architecture for when the brain becomes more computationally expensive (e.g., with temporal memory window analysis). This is the correct defensive engineering decision.

### 4.2 Thread Safety of `OrchardBrain` — Verified Safe

`OrchardBrain(enable_memory=False)` is stateless: `HealthAssessment`, `RiskAssessment`, and `RecommendationEngine` are all pure functions with no mutable instance state. Multiple concurrent calls from `asyncio.to_thread()` are safe.

---

## 5. Future Readiness

### 5.1 Temporal Memory — Ready

The `OrchardBrain` constructor accepts `enable_memory=True`. Activating it later requires only:
1. Changing the constructor call in `gateway/main.py`
2. Switching from `evaluate()` to `evaluate_orchestrated()` or `evaluate_full()`

The `OrchardMemory` class in [orchard_memory.py](file:///c:/Users/zonob/orchard-brain-core/src/orchard_brain/orchard_memory.py) already exists and tracks `SensorSnapshot` history. The integration path is clean.

> [!IMPORTANT]
> **Caveat:** If temporal memory is enabled, `OrchardBrain` becomes **stateful**. The current design of one `OrchardBrain` instance for all nodes would create cross-node memory contamination. You would need one `OrchardMemory` instance **per node_id**, managed in a dictionary within the service. This is not a current concern but should be documented.

### 5.2 Knowledge Graph — Ready

The `OrchardOrchestrator`, `OrchardGraph`, and multi-agent system (`disease_agent.py`, `water_agent.py`, `nutrition_agent.py`, `flowering_agent.py`, `yield_agent.py`) are all present in the codebase. Activating them requires switching to `evaluate_orchestrated()` and persisting the richer `OrchestratorResult` structure instead of `BrainResult`.

The database schema would need extension to store agent-level findings, but the existing `metadata_json` JSONB fields provide an escape hatch.

### 5.3 Machine Learning — Partially Ready

The codebase has no ML infrastructure, but the architecture supports it:
- Historical sensor data accumulates in TimescaleDB (ideal for time-series ML)
- Health scores and risk labels provide supervised training targets
- The `metadata_json` JSONB column allows storing ML confidence scores alongside rule-based outputs

An ML layer would sit **alongside** the rule engine (ensemble pattern), not replace it.

---

## 6. Summary of Findings

### Design Flaws (must fix before implementation)

| # | Severity | Finding | Location |
|---|---|---|---|
| 1 | **High** | Brain evaluation inside sync `_on_receive` callback — thread/async boundary violation | [service.py:53](file:///c:/Users/zonob/orchard-brain-core/gateway/service.py#L53) |
| 2 | **High** | Single long-lived DB session will accumulate stale state and break on transaction failure | [service.py](file:///c:/Users/zonob/orchard-brain-core/gateway/service.py) constructor |
| 3 | **Critical** | `save_orchestrator_result` expects `risk["type"]`/`risk["description"]` but brain returns `risk["risk"]`/`risk["message"]` — **will crash** | [repository.py:77-85](file:///c:/Users/zonob/orchard-brain-core/database/repository.py#L77-L85) |

### Technical Debt (acceptable for Phase 2D, track for future)

| # | Finding |
|---|---|
| 1 | `soil_moisture` not passed to brain; `humidity` used as VWC proxy |
| 2 | `rainfall` data collected but never consumed by brain |
| 3 | No backpressure/durability between radio receive and brain processing |
| 4 | Per-node `OrchardMemory` isolation not implemented (needed when memory is enabled) |

### Missing Components (not required for Phase 2D)

| # | Component | Needed When |
|---|---|---|
| 1 | Ingestion queue (durable buffer between radio and brain) | Production hardening |
| 2 | Per-node memory isolation dictionary | Temporal memory activation |
| 3 | ML feature store / training pipeline | ML phase |

---

## 7. Revised Recommendation for Implementation Plan

> [!IMPORTANT]
> **Before proceeding with Phase 2D implementation, the plan should be updated to address Flaws #1, #2, and #3:**
>
> 1. **Decouple `_on_receive` from processing** — use an `asyncio.Queue` as an intermediate buffer. The callback enqueues; a coroutine dequeues and processes.
> 2. **Use a session factory** — inject `async_sessionmaker` into `GatewayService` instead of a pre-built session. Create fresh sessions per processing cycle.
> 3. **Fix the `BrainResult` → DB key mapping** — either fix `save_orchestrator_result` to use `risk["risk"]`/`risk["message"]`, or create a new `save_brain_result` method with the correct contract.
>
> All three fixes are small (< 30 lines each) and eliminate runtime crashes and architectural fragility.


# Phase 2D Walkthrough: OrchardBrain Integration

This document summarizes the changes made to integrate the deterministic `OrchardBrain` intelligence engine into the `GatewayService` to evaluate incoming sensor readings.

## 1. Architectural Changes

### `asyncio.Queue` Ingestion Pipeline
The `GatewayService._on_receive` method now immediately hands off processing of `PKT_TYPE_DATA_UPLINK` messages using an `asyncio.Queue`. 

This solves the synchronous/asynchronous mismatch problem inherent in `TransportInterface` callbacks.

```python
    def _on_receive(self, raw_bytes: bytes, rssi: int):
        # ...
        if pkt_type == PKT_TYPE_DATA_UPLINK:
            # Non-blocking enqueue
            self._reading_queue.put_nowait((src, payload))
```

### AsyncSession Transient Lifecycle
We migrated `GatewayService` to accept `async_sessionmaker` instead of a long-lived `DatabaseRepository`. 

Each background loop—`_process_readings`, `_poll_loop`, and `_timeout_loop`—creates fresh, independent `AsyncSession` contexts during processing, preventing stale data and connection drops.

```python
        async with self.session_factory() as session:
            repo = DatabaseRepository(session)
            # execute DB logic...
```

### Deterministic `OrchardBrain` Threading
The `OrchardBrain` executes heavy mathematical evaluations (including risks and recommendation generation). To prevent blocking the main asyncio event loop, this process is mapped via a ThreadPool executor.

```python
        # Evaluate using deterministic brain inside a thread pool
        brain_result = await asyncio.to_thread(self.brain.evaluate, reading)
```

## 2. Database Integration

A new `save_brain_result` function was implemented in `DatabaseRepository` to correctly serialize the structured dictionaries returned by the engine, translating the internal key signatures into persistence models.

```python
        for risk in brain_result.get("risks", []):
            risk_model = RiskModel(
                time=dt,
                node_id=node_id,
                risk_type=risk["risk"],         # Mapped properly
                severity=risk["severity"],
                description=risk["message"]     # Mapped properly
            )
            self.session.add(risk_model)
```

## 3. Test Integration

A comprehensive integration test `test_gateway_service_uplink_processing` was added to verify the complete intelligence pipeline. 

The test creates a mock `DATA_UPLINK` frame with a critically high temperature value of `40.0 °C`.

> [!TIP]
> Testing revealed a critical concurrency failure related to `StaticPool` when utilizing an in-memory SQLite (`:memory:`) across multiple concurrent asyncio tasks. Testing infrastructure was migrated to leverage isolated file-backed test databases (`test_gateway.db`), resolving lock exceptions.

### Verification Results
Running the full suite:

```bash
python -m pytest
```

Result: **241 passed in 3.31s**

The full test suite guarantees that both Phase 2C Command and Queueing structures and Phase 2D intelligence hooks remain perfectly intact.
