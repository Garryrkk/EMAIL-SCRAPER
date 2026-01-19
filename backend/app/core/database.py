import logging
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from app.core.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

# Import models so metadata is populated when tables are created
from app.users.model import User
from app.people.model import Person
from app.emails.model import Email
from app.companies.model import Company

# Global session factory and engine
_session_factory: async_sessionmaker = None
_engine = None


async def init_db():
    global _engine, _session_factory

    pool_class = NullPool if settings.ENVIRONMENT == "test" else None

    engine_kwargs = {
        "echo": settings.DEBUG,
        "pool_pre_ping": True,
    }

    is_sqlite = settings.DATABASE_URL.startswith("sqlite")

    if pool_class:
        engine_kwargs["poolclass"] = pool_class
    elif not is_sqlite:
        # Only apply pool sizing for non-SQLite engines
        engine_kwargs.update(
            {
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_MAX_OVERFLOW,
                "pool_recycle": settings.DB_POOL_RECYCLE,
            }
        )

    _engine = create_async_engine(
        settings.DATABASE_URL,
        **engine_kwargs,
    )

    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    # --- Create tables ---
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized")


async def close_db():
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("Database connections closed")


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Provide an async session for FastAPI dependencies."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db():
    """FastAPI dependency for getting a database session."""
    async with get_session() as session:
        yield session
