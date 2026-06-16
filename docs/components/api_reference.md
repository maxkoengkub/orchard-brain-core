# Phase 2B Walkthrough: FastAPI Backend

The Orchard Brain FastAPI Backend has been successfully implemented and integrated with the Phase 2A TimescaleDB layer.

## Directory Structure
The API was implemented in a clean, modular structure at the repository root:
```text
api/
├── __init__.py
├── main.py              # Application bootstrap and OpenAPI configuration
├── dependencies.py      # Database session injection
├── schemas.py           # Pydantic models for request/response serialization
├── routers/
│   ├── __init__.py
│   ├── control.py       # Actuation and configuration endpoints
│   ├── intelligence.py  # Recommendations and risks endpoints
│   ├── nodes.py         # Node status endpoints
│   └── sensors.py       # Telemetry endpoints
└── tests/
    ├── __init__.py
    ├── conftest.py      # Test fixtures and in-memory SQLite DB override
    └── test_endpoints.py# Integration test suite
```

## Endpoints Deployed
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | System diagnostics. |
| `GET` | `/sensor-history` | Paged telemetry queries with `node_id` and `limit` filters. |
| `GET` | `/recommendations` | OrchardBrain output queries. |
| `GET` | `/risk-summary` | Historical risk evaluation queries. |
| `GET` | `/nodes` | Fleet status. |
| `POST` | `/commands` | Actuation queuing (writes `PENDING` to DB). |
| `POST` | `/configuration` | Configuration staging. |

## OpenAPI Configuration
The FastAPI application automatically generates OpenAPI (Swagger) documentation available at `/docs`. The app is configured with:
- **Title**: Orchard Brain API
- **Version**: 0.1.0
- **Description**: Phase 2B API for telemetry access and command dispatch.
- **Middleware**: Full CORS support enabled to allow immediate Phase 2C (Dashboard) integrations.

## Command Queue Implementation Details
Per the architectural requirement, `POST /commands` and `POST /configuration` **do not** interact with the LoRa hardware. Instead, they operate strictly via database queuing:
1. `POST /commands` accepts an `ActuationCommand` payload and uses the `DatabaseRepository` to insert it into the `CommandHistoryModel` with a `status="PENDING"`.
2. `POST /configuration` accepts a `ConfigPush` and inserts it as a `SystemEventModel` with `event_type="CONFIG_PUSH"`.
3. The API immediately returns a HTTP `202 Accepted` response with `status: QUEUED`.

This DB-driven queue allows the Gateway service to safely poll the database and manage the complex RF transmission lifecycle (acks, retries, duty-cycle compliance) asynchronously without blocking the REST API.

## Test Results
Comprehensive integration tests were written using `pytest`, `pytest-asyncio`, and `httpx`. The tests use dependency injection (`app.dependency_overrides`) to mock the database session with a local, in-memory `sqlite+aiosqlite` instance for total test isolation.

```text
============================= test session starts =============================
platform win32 -- Python 3.10.11, pytest-9.1.0, pluggy-1.6.0
rootdir: C:\Users\zonob\orchard-brain-core
configfile: pyproject.toml
plugins: anyio-4.13.0, langsmith-0.8.3, asyncio-1.4.0
asyncio: mode=strict, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 6 items

api\tests\test_endpoints.py ......                                       [100%]

============================== 6 passed in 0.21s ==============================
```
