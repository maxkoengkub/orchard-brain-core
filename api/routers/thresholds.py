from fastapi import APIRouter, Depends
from typing import List
from database.threshold_repository import ThresholdRepository
from api.dependencies import get_threshold_repository
from api.schemas import DynamicThresholdResponse

router = APIRouter(prefix="/thresholds", tags=["Thresholds"])

@router.get("/", response_model=List[DynamicThresholdResponse])
async def get_all_thresholds(repo: ThresholdRepository = Depends(get_threshold_repository)):
    """Retrieve all dynamic thresholds."""
    return await repo.get_all_thresholds()

@router.get("/{parameter_name}", response_model=List[DynamicThresholdResponse])
async def get_thresholds_by_parameter(parameter_name: str, repo: ThresholdRepository = Depends(get_threshold_repository)):
    """Retrieve dynamic thresholds for a specific parameter."""
    return await repo.get_thresholds_by_parameter(parameter_name)
