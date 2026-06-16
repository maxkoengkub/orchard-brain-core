from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import sensors, intelligence, nodes, control, knowledge, evidence, thresholds, epochs
from database.config import FF_KNOWLEDGE_UI, FF_EVIDENCE_ENGINE, USE_DYNAMIC_THRESHOLDS, FF_EPOCH_MANAGEMENT

app = FastAPI(
    title="Orchard Brain API",
    description="Phase 2B API for telemetry access and command dispatch.",
    version="0.1.0"
)

# Allow dashboard integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "service": "orchard-brain-api"}

app.include_router(sensors.router)
app.include_router(intelligence.router)
app.include_router(nodes.router)
app.include_router(control.router)

if FF_KNOWLEDGE_UI:
    app.include_router(knowledge.router)

if FF_EVIDENCE_ENGINE:
    app.include_router(evidence.router)

if USE_DYNAMIC_THRESHOLDS:
    app.include_router(thresholds.router)

if FF_EPOCH_MANAGEMENT:
    app.include_router(epochs.router)
