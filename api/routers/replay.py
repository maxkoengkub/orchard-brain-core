from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Optional
from database.replay_repository import ReplayRepository
from api.dependencies import get_replay_repository
from api.schemas import ReplayJobCreate, ReplayJobResponse, ReplayResultResponse
from src.orchard_brain.knowledge.replay_engine import ReplayEngine

router = APIRouter(prefix="/replay", tags=["Replay Engine"])

def get_replay_engine(repo: ReplayRepository = Depends(get_replay_repository)) -> ReplayEngine:
    return ReplayEngine(repo)

@router.post("/jobs", response_model=ReplayJobResponse)
async def start_replay_job(job_req: ReplayJobCreate, engine: ReplayEngine = Depends(get_replay_engine)):
    """Create a new replay job. (Execution would ideally be asynchronous)"""
    try:
        return await engine.start_job(
            target_epoch_id=job_req.target_epoch_id,
            start_time=job_req.start_telemetry_time,
            end_time=job_req.end_telemetry_time
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/jobs/{job_id}", response_model=ReplayJobResponse)
async def get_replay_job(job_id: int, engine: ReplayEngine = Depends(get_replay_engine)):
    """Get the status of a replay job."""
    try:
        job = await engine.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/jobs/{job_id}/results", response_model=List[ReplayResultResponse])
async def get_replay_results(job_id: int, engine: ReplayEngine = Depends(get_replay_engine)):
    """Get the full results of a replay job."""
    try:
        return await engine.get_job_results(job_id)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
