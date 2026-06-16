from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, update, delete
from datetime import datetime, timezone
import json
from typing import Optional, List

from database.models import KnowledgeSourceModel, TrustTier

class KnowledgeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, limit: int = 100) -> List[KnowledgeSourceModel]:
        stmt = select(KnowledgeSourceModel).order_by(desc(KnowledgeSourceModel.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, source_id: int) -> Optional[KnowledgeSourceModel]:
        stmt = select(KnowledgeSourceModel).where(KnowledgeSourceModel.id == source_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, 
                     source_name: str, 
                     source_version: str, 
                     trust_tier: TrustTier, 
                     is_active: bool = True, 
                     metadata_json: Optional[dict] = None) -> KnowledgeSourceModel:
        source = KnowledgeSourceModel(
            source_name=source_name,
            source_version=source_version,
            trust_tier=trust_tier,
            is_active=is_active,
            metadata_json=metadata_json
        )
        self.session.add(source)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def update(self, source_id: int, updates: dict) -> Optional[KnowledgeSourceModel]:
        source = await self.get_by_id(source_id)
        if not source:
            return None
        
        for key, value in updates.items():
            if hasattr(source, key):
                setattr(source, key, value)
                
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def delete(self, source_id: int) -> bool:
        source = await self.get_by_id(source_id)
        if not source:
            return False
            
        await self.session.delete(source)
        await self.session.commit()
        return True
