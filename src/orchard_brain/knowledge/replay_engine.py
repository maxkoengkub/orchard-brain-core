from datetime import datetime
from typing import Optional, List
from database.replay_repository import ReplayRepository
from database.models import ReplayJobModel, ReplayResultModel
from database.config import FF_REPLAY_ENGINE
from src.orchard_brain.engine import OrchardBrain

class ReplayEngine:
    """Orchestrates historical telemetry replay against a specified epoch.
    
    Guarantees isolation:
    - Pure function evaluation via OrchardBrain.evaluate_raw()
    - Results saved only to DB (ReplayResultModel)
    - No CommandDispatcher emission possible.
    """
    
    def __init__(self, repository: ReplayRepository):
        self.repository = repository

    def _check_flag(self):
        if not FF_REPLAY_ENGINE:
            raise RuntimeError("FF_REPLAY_ENGINE is disabled.")

    async def start_job(self, target_epoch_id: int, start_time: datetime, end_time: datetime) -> ReplayJobModel:
        self._check_flag()
        job = await self.repository.create_job(target_epoch_id, start_time, end_time)
        return job

    async def get_job(self, job_id: int) -> Optional[ReplayJobModel]:
        self._check_flag()
        return await self.repository.get_job(job_id)

    async def get_job_results(self, job_id: int) -> List[ReplayResultModel]:
        self._check_flag()
        return await self.repository.get_results(job_id)

    async def run_job(self, job_id: int, mock_telemetry: List[dict]):
        """Executes the pure mathematical evaluation for a given job.
        
        Args:
            job_id: The ID of the ReplayJob.
            mock_telemetry: A list of dicts simulating DB records:
                            [{"timestamp": dt, "temp": 25.0, "hum": 60.0, "ec": 1.2, "ph": 6.0}]
                            
        Note: In a full system, this would query a real telemetry table.
        For this milestone, we allow passing it explicitly to demonstrate the isolated call chain.
        """
        self._check_flag()
        
        job = await self.repository.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
            
        await self.repository.update_job_status(job_id, "RUNNING")
        
        try:
            for record in mock_telemetry:
                # Instantiate a pure, stateless brain
                brain = OrchardBrain()
                
                # Execute the pure function
                result = brain.evaluate_raw(
                    temperature=record.get("temp", 0.0),
                    humidity=record.get("hum", 0.0),
                    ec=record.get("ec", 0.0),
                    ph=record.get("ph", 0.0)
                )
                
                # Save purely to the database repository
                await self.repository.save_result(
                    job_id=job_id,
                    telemetry_timestamp=record["timestamp"],
                    result_payload=result
                )
                
            await self.repository.update_job_status(job_id, "COMPLETED")
        except Exception as e:
            await self.repository.update_job_status(job_id, f"FAILED: {str(e)}")
            raise e
