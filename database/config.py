import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Using an environment variable or falling back to a default testing db
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql+asyncpg://postgres:postgres@localhost:5432/orchard_brain"
)
SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")

FF_KNOWLEDGE_UI = os.environ.get("FF_KNOWLEDGE_UI", "false").lower() == "true"
FF_EVIDENCE_ENGINE = os.environ.get("FF_EVIDENCE_ENGINE", "false").lower() == "true"
USE_DYNAMIC_THRESHOLDS = os.environ.get("USE_DYNAMIC_THRESHOLDS", "false").lower() == "true"

# Async Engine for FastAPI/Gateway
async_engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)

# Sync Engine for Alembic and blocking operations
sync_engine = create_engine(SYNC_DATABASE_URL, echo=False)
SyncSessionLocal = sessionmaker(bind=sync_engine, class_=Session)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
