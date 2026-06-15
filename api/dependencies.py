from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from database.config import AsyncSessionLocal
from database.repository import DatabaseRepository

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def get_repository() -> AsyncGenerator[DatabaseRepository, None]:
    async with AsyncSessionLocal() as session:
        yield DatabaseRepository(session)
