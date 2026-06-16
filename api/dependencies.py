from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from database.config import AsyncSessionLocal
from database.repository import DatabaseRepository
from database.knowledge_repository import KnowledgeRepository
from database.evidence_repository import EvidenceRepository
from database.threshold_repository import ThresholdRepository
from database.epoch_repository import EpochRepository

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def get_repository() -> AsyncGenerator[DatabaseRepository, None]:
    async with AsyncSessionLocal() as session:
        yield DatabaseRepository(session)

async def get_knowledge_repository() -> AsyncGenerator[KnowledgeRepository, None]:
    async with AsyncSessionLocal() as session:
        yield KnowledgeRepository(session)

async def get_evidence_repository() -> AsyncGenerator[EvidenceRepository, None]:
    async with AsyncSessionLocal() as session:
        yield EvidenceRepository(session)

async def get_threshold_repository() -> AsyncGenerator[ThresholdRepository, None]:
    async with AsyncSessionLocal() as session:
        yield ThresholdRepository(session)

async def get_epoch_repository() -> AsyncGenerator[EpochRepository, None]:
    async with AsyncSessionLocal() as session:
        yield EpochRepository(session)
