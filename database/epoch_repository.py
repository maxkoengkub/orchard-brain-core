from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from typing import List, Optional

from database.models import KnowledgeEpochModel, ActiveEpochPointerModel

class EpochRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_epoch(self, name: str, description: Optional[str] = None) -> KnowledgeEpochModel:
        """Create a new immutable epoch."""
        epoch = KnowledgeEpochModel(name=name, description=description)
        self.session.add(epoch)
        await self.session.commit()
        await self.session.refresh(epoch)
        return epoch

    async def get_active_epoch(self) -> Optional[KnowledgeEpochModel]:
        """Fetch the currently active epoch linked by the singleton pointer."""
        stmt = select(ActiveEpochPointerModel).where(ActiveEpochPointerModel.id == 1)
        result = await self.session.execute(stmt)
        pointer = result.scalars().first()
        if pointer and pointer.epoch_id:
            epoch_stmt = select(KnowledgeEpochModel).where(KnowledgeEpochModel.id == pointer.epoch_id)
            epoch_result = await self.session.execute(epoch_stmt)
            return epoch_result.scalars().first()
        return None

    async def set_active_epoch(self, epoch_id: int) -> ActiveEpochPointerModel:
        """Update the singleton pointer. O(1) rollback."""
        stmt = update(ActiveEpochPointerModel).where(ActiveEpochPointerModel.id == 1).values(epoch_id=epoch_id)
        await self.session.execute(stmt)
        await self.session.commit()
        
        # Return updated pointer
        fetch_stmt = select(ActiveEpochPointerModel).where(ActiveEpochPointerModel.id == 1)
        result = await self.session.execute(fetch_stmt)
        return result.scalars().first()

    async def get_all_epochs(self) -> List[KnowledgeEpochModel]:
        """Retrieve all epochs."""
        stmt = select(KnowledgeEpochModel).order_by(KnowledgeEpochModel.id.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
