from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from database.config import AsyncSessionLocal
from database.repository import DatabaseRepository
from database.knowledge_repository import KnowledgeRepository

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def get_repository() -> AsyncGenerator[DatabaseRepository, None]:
    async with AsyncSessionLocal() as session:
        yield DatabaseRepository(session)

async def get_knowledge_repository() -> AsyncGenerator[KnowledgeRepository, None]:
    async with AsyncSessionLocal() as session:
        yield KnowledgeRepository(session)
