from typing import Optional, List
from database.epoch_repository import EpochRepository
from database.config import FF_EPOCH_MANAGEMENT
from database.models import KnowledgeEpochModel, ActiveEpochPointerModel

class EpochManager:
    """Manages epoch versioning and active pointer logic.
    
    Checks FF_EPOCH_MANAGEMENT feature flag.
    Provides O(1) rollback and strict singleton tracking.
    """
    
    def __init__(self, repository: EpochRepository):
        self.repository = repository

    def _check_flag(self):
        if not FF_EPOCH_MANAGEMENT:
            raise RuntimeError("FF_EPOCH_MANAGEMENT is disabled.")

    async def get_active_epoch(self) -> Optional[KnowledgeEpochModel]:
        """Fetch active epoch if flag is enabled."""
        self._check_flag()
        return await self.repository.get_active_epoch()

    async def list_epochs(self) -> List[KnowledgeEpochModel]:
        """List all epochs."""
        self._check_flag()
        return await self.repository.get_all_epochs()

    async def create_epoch(self, name: str, description: Optional[str] = None) -> KnowledgeEpochModel:
        """Create a new epoch."""
        self._check_flag()
        return await self.repository.create_epoch(name, description)

    async def set_active_epoch(self, epoch_id: int) -> ActiveEpochPointerModel:
        """Point the active epoch to a given ID. O(1) Rollback."""
        self._check_flag()
        return await self.repository.set_active_epoch(epoch_id)
