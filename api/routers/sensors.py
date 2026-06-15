from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from database.repository import DatabaseRepository
from api.dependencies import get_repository
from api.schemas import SensorHistoryResponse

router = APIRouter(prefix="/sensor-history", tags=["Sensors"])

@router.get("", response_model=List[SensorHistoryResponse])
async def get_sensor_history(
    node_id: Optional[int] = None,
    limit: int = Query(100, le=1000),
    repo: DatabaseRepository = Depends(get_repository)
):
    """Retrieve historical sensor data."""
    readings = await repo.get_sensor_history(node_id=node_id, limit=limit)
    return readings
