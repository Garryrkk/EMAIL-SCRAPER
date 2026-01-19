import logging
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from app.core.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

# --- Import the actual SQLAlchemy models from your routes folder ---
from app.api.routes.people import Person
from app.api.routes.emails import Email
from app.api.routes.companies import Company

# Global session factory and engine
_session_factory: async_sessionmaker = None
_engine = None


async def init_db():
    global _engine, _session_factory

    pool_class = NullPool if settings.ENVIRONMENT == "test" else None

    _engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        poolclass=pool_class,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
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
async def get_db_session():
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



async def get_session() -> AsyncSession:
    """Dependency for FastAPI to inject async DB session."""
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
