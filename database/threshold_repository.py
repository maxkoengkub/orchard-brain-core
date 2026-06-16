from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from database.models import DynamicThresholdModel

class ThresholdRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_thresholds_by_parameter(self, parameter_name: str) -> List[DynamicThresholdModel]:
        """Fetch all dynamic thresholds for a given parameter."""
        stmt = select(DynamicThresholdModel).where(DynamicThresholdModel.parameter_name == parameter_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
        
    async def get_all_thresholds(self) -> List[DynamicThresholdModel]:
        """Fetch all dynamic thresholds."""
        stmt = select(DynamicThresholdModel)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_threshold(self, 
                            parameter_name: str,
                            confidence_score: float,
                            source_id: int,
                            optimal_min: Optional[float] = None,
                            optimal_max: Optional[float] = None,
                            warn_min: Optional[float] = None,
                            warn_max: Optional[float] = None,
                            critical_min: Optional[float] = None,
                            critical_max: Optional[float] = None,
                            evidence_id: Optional[int] = None,
                            knowledge_epoch_id: Optional[int] = None) -> DynamicThresholdModel:
        """Add a new evidence-backed threshold. Read-only design implies we don't update existing ones."""
        threshold = DynamicThresholdModel(
            parameter_name=parameter_name,
            confidence_score=confidence_score,
            source_id=source_id,
            optimal_min=optimal_min,
            optimal_max=optimal_max,
            warn_min=warn_min,
            warn_max=warn_max,
            critical_min=critical_min,
            critical_max=critical_max,
            evidence_id=evidence_id,
            knowledge_epoch_id=knowledge_epoch_id
        )
        self.session.add(threshold)
        await self.session.commit()
        await self.session.refresh(threshold)
        return threshold
