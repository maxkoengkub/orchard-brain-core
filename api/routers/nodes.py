from fastapi import APIRouter, Depends
from typing import List
from database.repository import DatabaseRepository
from api.dependencies import get_repository
from api.schemas import NodeStatusResponse

router = APIRouter(prefix="/nodes", tags=["Nodes"])

@router.get("", response_model=List[NodeStatusResponse])
async def get_nodes(
    repo: DatabaseRepository = Depends(get_repository)
):
    """Retrieve the latest status of all registered LoRa nodes."""
    nodes = await repo.get_nodes()
    return nodes
