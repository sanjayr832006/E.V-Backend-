import logging
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

logger = logging.getLogger("ev_backend")

Base = declarative_base()

# Engine & Sessionmaker placeholders
engine = None
AsyncSessionLocal = None
ACTIVE_DB_TYPE = "sqlite"

async def init_db():
    """
    Initializes the database engine safely.
    Creates all defined database tables.
    """
    global engine, AsyncSessionLocal, ACTIVE_DB_TYPE
    
    try:
        engine = create_async_engine("sqlite+aiosqlite:///./ev_assistant.db", echo=False)
        AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        ACTIVE_DB_TYPE = "sqlite"
        logger.info("✅ Database initialized successfully!")
    except Exception as e:
        logger.warning(f"Database init note: {e}")
        ACTIVE_DB_TYPE = "none"

async def get_db() -> AsyncGenerator[Optional[AsyncSession], None]:
    """
    Dependency generator for FastAPI routes to obtain a database session safely.
    """
    session = None
    if AsyncSessionLocal is not None:
        try:
            session = AsyncSessionLocal()
        except Exception as e:
            logger.warning(f"Session creation note: {e}")
            session = None

    yield session

    if session is not None:
        try:
            await session.close()
        except Exception:
            pass
