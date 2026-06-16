from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from database.knowledge_repository import KnowledgeRepository
from api.dependencies import get_knowledge_repository
from api.schemas import KnowledgeSourceCreate, KnowledgeSourceUpdate, KnowledgeSourceResponse

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])

@router.get("/sources", response_model=List[KnowledgeSourceResponse])
async def list_knowledge_sources(repo: KnowledgeRepository = Depends(get_knowledge_repository)):
    """List all knowledge sources."""
    sources = await repo.get_all()
    return sources

@router.get("/sources/{source_id}", response_model=KnowledgeSourceResponse)
async def get_knowledge_source(source_id: int, repo: KnowledgeRepository = Depends(get_knowledge_repository)):
    """Get a specific knowledge source by ID."""
    source = await repo.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    return source

@router.post("/sources", response_model=KnowledgeSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_source(
    source_in: KnowledgeSourceCreate,
    repo: KnowledgeRepository = Depends(get_knowledge_repository)
):
    """Create a new knowledge source."""
    source = await repo.create(
        source_name=source_in.source_name,
        source_version=source_in.source_version,
        trust_tier=source_in.trust_tier,
        is_active=source_in.is_active,
        metadata_json=source_in.metadata_json
    )
    return source

@router.put("/sources/{source_id}", response_model=KnowledgeSourceResponse)
async def update_knowledge_source(
    source_id: int,
    source_in: KnowledgeSourceUpdate,
    repo: KnowledgeRepository = Depends(get_knowledge_repository)
):
    """Update an existing knowledge source."""
    updates = source_in.model_dump(exclude_unset=True)
    source = await repo.update(source_id, updates)
    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    return source

@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_source(source_id: int, repo: KnowledgeRepository = Depends(get_knowledge_repository)):
    """Delete a knowledge source."""
    success = await repo.delete(source_id)
    if not success:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
