from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from typing import List, Optional
from datetime import datetime

from database.models import ReplayJobModel, ReplayResultModel

class ReplayRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_job(self, target_epoch_id: int, start_telemetry_time: datetime, end_telemetry_time: datetime) -> ReplayJobModel:
        """Create a new replay job."""
        job = ReplayJobModel(
            target_epoch_id=target_epoch_id,
            start_telemetry_time=start_telemetry_time,
            end_telemetry_time=end_telemetry_time,
            status="PENDING"
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def update_job_status(self, job_id: int, status: str) -> ReplayJobModel:
        """Update job status."""
        stmt = update(ReplayJobModel).where(ReplayJobModel.id == job_id).values(status=status)
        await self.session.execute(stmt)
        await self.session.commit()
        
        fetch_stmt = select(ReplayJobModel).where(ReplayJobModel.id == job_id)
        result = await self.session.execute(fetch_stmt)
        return result.scalars().first()

    async def get_job(self, job_id: int) -> Optional[ReplayJobModel]:
        """Fetch a specific replay job."""
        stmt = select(ReplayJobModel).where(ReplayJobModel.id == job_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def save_result(self, job_id: int, telemetry_timestamp: datetime, result_payload: dict) -> ReplayResultModel:
        """Save a single evaluation result from a replay."""
        # Convert internal domain models (like risks, recommendations) to JSON serializable formats
        risks_list = [r.__dict__ for r in result_payload.get('risks', [])]
        recs_list = [r.__dict__ for r in result_payload.get('recommendations', [])]
        
        eval_payload = {
            "health_score": result_payload.get('health_score'),
            "water_stress": result_payload.get('water_stress'),
            "nutrient_stress": result_payload.get('nutrient_stress'),
            "risks": risks_list,
            "recommendations": recs_list
        }
        
        result = ReplayResultModel(
            job_id=job_id,
            telemetry_timestamp=telemetry_timestamp,
            health_score=result_payload.get('health_score'),
            water_stress=result_payload.get('water_stress'),
            nutrient_stress=result_payload.get('nutrient_stress'),
            risks_count=len(risks_list),
            recommendations_count=len(recs_list),
            evaluation_payload=eval_payload
        )
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def get_results(self, job_id: int) -> List[ReplayResultModel]:
        """Fetch all results for a job."""
        stmt = select(ReplayResultModel).where(ReplayResultModel.job_id == job_id).order_by(ReplayResultModel.telemetry_timestamp)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
