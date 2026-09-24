import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

logger = logging.getLogger("ev_backend")

Base = declarative_base()

# Engine & Sessionmaker placeholders
engine = None
AsyncSessionLocal = None
ACTIVE_DB_TYPE = "postgresql"

async def init_db():
    """
    Initializes the database engine (PostgreSQL by default, with SQLite dynamic fallback).
    Creates all defined database tables.
    """
    global engine, AsyncSessionLocal, ACTIVE_DB_TYPE
    
    db_url = settings.DATABASE_URL
    try:
        logger.info(f"Connecting to PostgreSQL database: {db_url.split('@')[-1] if '@' in db_url else db_url}")
        engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
        AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ PostgreSQL Database connected and tables initialized successfully!")
        ACTIVE_DB_TYPE = "postgresql"
    except Exception as e:
        logger.warning(f"PostgreSQL connection failed ({e}). Falling back to local SQLite database...")
        fallback_url = "sqlite+aiosqlite:///./ev_assistant.db"
        engine = create_async_engine(fallback_url, echo=False)
        AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ SQLite Fallback Database initialized successfully!")
        ACTIVE_DB_TYPE = "sqlite"

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency generator for FastAPI routes to obtain a database session.
    """
    if AsyncSessionLocal is None:
        await init_db()
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
