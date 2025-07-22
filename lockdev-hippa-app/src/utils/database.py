"""
Database utilities for HIPAA-compliant application.
"""
import os
from typing import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base


logger = structlog.get_logger()

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/hipaa_db",
)

# Use sqlite for testing if database URL is not provided
if os.getenv("ENVIRONMENT") == "testing":
    DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create async session factory
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Create declarative base
Base = declarative_base()


def get_database_url() -> str:
    """Get database URL."""
    return DATABASE_URL


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with async_session() as session:
        try:
            yield session
        except Exception as e:
            logger.error("Database session error", error=str(e))
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_database() -> None:
    """Initialize database tables."""
    try:
        # Import models to register them
        from ..models.user import User  # noqa: F401
        from ..models.audit_log import AuditLog  # noqa: F401

        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        raise


async def close_database() -> None:
    """Close database connections."""
    await engine.dispose()
    logger.info("Database connections closed")
