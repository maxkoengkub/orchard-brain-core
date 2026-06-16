from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from typing import List, Optional

from database.models import RiskEvidenceModel, RecommendationEvidenceModel

class EvidenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_risk_evidence(self, 
                                risk_id: int, 
                                source_id: int, 
                                rule_key: str, 
                                rule_version: str, 
                                confidence_weight: float, 
                                knowledge_epoch_id: Optional[int] = None,
                                context_json: Optional[dict] = None) -> RiskEvidenceModel:
        """Add a new evidence record for a risk. Evidence is strictly append-only."""
        evidence = RiskEvidenceModel(
            risk_id=risk_id,
            source_id=source_id,
            knowledge_epoch_id=knowledge_epoch_id,
            rule_key=rule_key,
            rule_version=rule_version,
            confidence_weight=confidence_weight,
            context_json=context_json
        )
        self.session.add(evidence)
        await self.session.commit()
        await self.session.refresh(evidence)
        return evidence

    async def add_recommendation_evidence(self, 
                                          recommendation_id: int, 
                                          source_id: int, 
                                          rule_key: str, 
                                          rule_version: str, 
                                          confidence_weight: float, 
                                          knowledge_epoch_id: Optional[int] = None,
                                          context_json: Optional[dict] = None) -> RecommendationEvidenceModel:
        """Add a new evidence record for a recommendation. Evidence is strictly append-only."""
        evidence = RecommendationEvidenceModel(
            recommendation_id=recommendation_id,
            source_id=source_id,
            knowledge_epoch_id=knowledge_epoch_id,
            rule_key=rule_key,
            rule_version=rule_version,
            confidence_weight=confidence_weight,
            context_json=context_json
        )
        self.session.add(evidence)
        await self.session.commit()
        await self.session.refresh(evidence)
        return evidence

    async def get_evidence_for_risk(self, risk_id: int, limit: int = 100) -> List[RiskEvidenceModel]:
        """Retrieve all provenance records for a given risk."""
        stmt = select(RiskEvidenceModel).where(RiskEvidenceModel.risk_id == risk_id).order_by(desc(RiskEvidenceModel.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_evidence_for_recommendation(self, recommendation_id: int, limit: int = 100) -> List[RecommendationEvidenceModel]:
        """Retrieve all provenance records for a given recommendation."""
        stmt = select(RecommendationEvidenceModel).where(RecommendationEvidenceModel.recommendation_id == recommendation_id).order_by(desc(RecommendationEvidenceModel.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
