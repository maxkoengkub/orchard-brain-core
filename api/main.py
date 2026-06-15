from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import sensors, intelligence, nodes, control

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
