# Phase 2 Tasks

# Task List: Phase 2D Orchard Brain Integration

- `[x]` **Implement `save_brain_result` in `DatabaseRepository`**
  - Create the new method mapped with correct keys (`risk`, `message` etc.).
  - Ensure backwards compatibility with `save_orchestrator_result`.
- `[x]` **Update `GatewayService` core**
  - Accept `session_factory` instead of `repository`.
  - Accept `OrchardBrain` instance.
  - Implement `asyncio.Queue` for reading ingestion.
  - Update `_on_receive` to queue `PKT_TYPE_DATA_UPLINK` packets.
  - Create `_process_readings()` coroutine.
  - Update `_poll_loop` and ACK handling to use transient sessions.
- `[x]` **Update `gateway/main.py`**
  - Inject `async_sessionmaker` into `GatewayService`.
  - Inject stateless `OrchardBrain(enable_memory=False)` into `GatewayService`.
- `[x]` **Update tests in `test_service.py`**
  - Fix test dependencies to provide `session_factory` and `OrchardBrain`.
  - Add an integration test that sends a `DATA_UPLINK` payload.
  - Verify DB outputs: `SensorReadingModel`, `OrchardHealthModel`, `RiskModel`, `RecommendationModel`.
- `[x]` **Verification**
  - Run all tests (`database`, `api`, `gateway`).
  - Update walkthrough.


# Phase 3A.5 Tasks

- `[ ]` 1. **ThresholdEngine Contract**
  - Update `src/orchard_brain/knowledge/threshold_engine.py`
  - Define `PARAM_` constants.
  - Define `ThresholdBounds` and `ThresholdMap`.
  - Implement `get_all_thresholds(epoch_id)` merging fallback logic and dynamic DB rows.

- `[ ]` 2. **OrchardBrain Facades**
  - Update `src/orchard_brain/engine.py`
  - Add `evaluate_async(reading, epoch_id=None)`.
  - Add `evaluate_orchestrated_async(reading, epoch_id=None)`.
  - Add optional `thresholds=None` to `evaluate`, `evaluate_raw`, `evaluate_orchestrated`, `evaluate_full`.

- `[ ]` 3. **Assessors Update**
  - Update `src/orchard_brain/health.py`
  - Update `src/orchard_brain/risk.py`
  - Update `src/orchard_brain/recommendation.py`
  - Accept `thresholds=None` and use dictionary getters (e.g. `thresholds.get(PARAM_TEMPERATURE, {})`).

- `[ ]` 4. **Orchestrator and Agents**
  - Update `src/orchard_brain/orchard_orchestrator.py`
  - Update `src/orchard_brain/agents/water_agent.py`
  - Update `src/orchard_brain/agents/disease_agent.py`
  - Update `src/orchard_brain/agents/nutrition_agent.py`
  - Update `src/orchard_brain/agents/flowering_agent.py`
  - Update `src/orchard_brain/agents/yield_agent.py`
  - Cascade `thresholds` into `.analyze()`.

- `[ ]` 5. **Test Implementation**
  - Create `tests/test_dynamic_thresholds.py` with specific tests from the plan.
