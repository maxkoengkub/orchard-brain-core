from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from database.epoch_repository import EpochRepository
from api.dependencies import get_epoch_repository
from api.schemas import KnowledgeEpochResponse, KnowledgeEpochCreate, ActiveEpochUpdate
from src.orchard_brain.knowledge.epoch_manager import EpochManager

router = APIRouter(prefix="/epochs", tags=["Epochs"])

def get_epoch_manager(repo: EpochRepository = Depends(get_epoch_repository)) -> EpochManager:
    return EpochManager(repo)

@router.get("/", response_model=List[KnowledgeEpochResponse])
async def list_epochs(manager: EpochManager = Depends(get_epoch_manager)):
    """Retrieve all knowledge epochs."""
    try:
        return await manager.list_epochs()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/active", response_model=Optional[KnowledgeEpochResponse])
async def get_active_epoch(manager: EpochManager = Depends(get_epoch_manager)):
    """Retrieve active knowledge epoch."""
    try:
        return await manager.get_active_epoch()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/", response_model=KnowledgeEpochResponse)
async def create_epoch(epoch: KnowledgeEpochCreate, manager: EpochManager = Depends(get_epoch_manager)):
    """Create a new epoch."""
    try:
        return await manager.create_epoch(epoch.name, epoch.description)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/active")
async def set_active_epoch(update: ActiveEpochUpdate, manager: EpochManager = Depends(get_epoch_manager)):
    """Set active epoch pointer."""
    try:
        await manager.set_active_epoch(update.epoch_id)
        return {"status": "success", "active_epoch_id": update.epoch_id}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
