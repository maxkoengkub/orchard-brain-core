from fastapi import APIRouter, Depends
from typing import List
from database.evidence_repository import EvidenceRepository
from api.dependencies import get_evidence_repository
from api.schemas import RiskEvidenceResponse, RecommendationEvidenceResponse

router = APIRouter(prefix="/evidence", tags=["Evidence"])

@router.get("/risk/{risk_id}", response_model=List[RiskEvidenceResponse])
async def get_risk_evidence(risk_id: int, repo: EvidenceRepository = Depends(get_evidence_repository)):
    """Retrieve provenance records for a given risk."""
    evidence = await repo.get_evidence_for_risk(risk_id)
    return evidence

@router.get("/recommendation/{recommendation_id}", response_model=List[RecommendationEvidenceResponse])
async def get_recommendation_evidence(recommendation_id: int, repo: EvidenceRepository = Depends(get_evidence_repository)):
    """Retrieve provenance records for a given recommendation."""
    evidence = await repo.get_evidence_for_recommendation(recommendation_id)
    return evidence
