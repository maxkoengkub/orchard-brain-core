from typing import Optional, List
from database.evidence_repository import EvidenceRepository
from src.orchard_brain.knowledge.source_registry import SourceRegistry
from database.models import RiskEvidenceModel, RecommendationEvidenceModel

class EvidenceEngine:
    """Service layer for evidence management.
    
    This engine encapsulates provenance infrastructure and registry lookup logic.
    It does not integrate with or modify OrchardBrain's evaluation logic.
    """
    
    def __init__(self, repository: EvidenceRepository, registry: SourceRegistry):
        self.repository = repository
        self.registry = registry

    async def record_risk_evidence(self,
                                   risk_id: int,
                                   source_id: int,
                                   rule_key: str,
                                   rule_version: str,
                                   confidence_weight: float,
                                   knowledge_epoch_id: Optional[int] = None,
                                   context_json: Optional[dict] = None) -> RiskEvidenceModel:
        """Record evidence for a risk, ensuring the source is active in the registry."""
        source = self.registry.get_source(source_id)
        if not source:
            raise ValueError(f"Source {source_id} is not an active knowledge source.")
            
        return await self.repository.add_risk_evidence(
            risk_id=risk_id,
            source_id=source_id,
            rule_key=rule_key,
            rule_version=rule_version,
            confidence_weight=confidence_weight,
            knowledge_epoch_id=knowledge_epoch_id,
            context_json=context_json
        )

    async def record_recommendation_evidence(self,
                                             recommendation_id: int,
                                             source_id: int,
                                             rule_key: str,
                                             rule_version: str,
                                             confidence_weight: float,
                                             knowledge_epoch_id: Optional[int] = None,
                                             context_json: Optional[dict] = None) -> RecommendationEvidenceModel:
        """Record evidence for a recommendation, ensuring the source is active in the registry."""
        source = self.registry.get_source(source_id)
        if not source:
            raise ValueError(f"Source {source_id} is not an active knowledge source.")
            
        return await self.repository.add_recommendation_evidence(
            recommendation_id=recommendation_id,
            source_id=source_id,
            rule_key=rule_key,
            rule_version=rule_version,
            confidence_weight=confidence_weight,
            knowledge_epoch_id=knowledge_epoch_id,
            context_json=context_json
        )

    async def get_risk_provenance(self, risk_id: int) -> List[RiskEvidenceModel]:
        """Retrieve provenance for a specific risk."""
        return await self.repository.get_evidence_for_risk(risk_id)

    async def get_recommendation_provenance(self, recommendation_id: int) -> List[RecommendationEvidenceModel]:
        """Retrieve provenance for a specific recommendation."""
        return await self.repository.get_evidence_for_recommendation(recommendation_id)
