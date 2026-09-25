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
    Initializes the database engine (SQLite by default on cloud, PostgreSQL if configured).
    Creates all defined database tables.
    """
    global engine, AsyncSessionLocal, ACTIVE_DB_TYPE
    
    db_url = settings.DATABASE_URL
    db_file_path = "/tmp/ev_assistant.db" if (os.getenv("RENDER") or os.getenv("PORT")) else "./ev_assistant.db"

    if "localhost" in db_url or "127.0.0.1" in db_url:
        db_url = f"sqlite+aiosqlite:///{db_file_path}"

    try:
        if db_url.startswith("sqlite"):
            engine = create_async_engine(db_url, echo=False)
            ACTIVE_DB_TYPE = "sqlite"
        else:
            engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
            ACTIVE_DB_TYPE = "postgresql"

        AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(f"✅ Database initialized successfully using {ACTIVE_DB_TYPE}!")
    except Exception as e:
        logger.warning(f"Primary DB connection failed ({e}). Falling back to local SQLite database...")
        fallback_url = f"sqlite+aiosqlite:///{db_file_path}"
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
        try:
            await init_db()
        except Exception as e:
            logger.error(f"init_db error in get_db: {e}")

    if AsyncSessionLocal is not None:
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()
    else:
        yield None
