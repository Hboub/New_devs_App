import asyncio
import logging

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings

logger = logging.getLogger(__name__)


class DatabasePool:
    def __init__(self):
        self.engine = None
        self.session_factory = None
        self._init_lock = asyncio.Lock()

    async def initialize(self):
        """Initialize the connection pool once per process (safe to call repeatedly)."""
        if self.session_factory is not None:
            return

        async with self._init_lock:
            if self.session_factory is not None:
                return

            # FIX 1: the old URL was assembled from settings.supabase_db_* attributes
            # that don't exist in this environment, so every call raised AttributeError.
            # docker-compose provides DATABASE_URL; we only swap in the async driver.
            database_url = make_url(settings.database_url).set(
                drivername="postgresql+asyncpg"
            )

            # FIX 2: poolclass=QueuePool is a synchronous pool and SQLAlchemy refuses
            # it for async engines. The default (AsyncAdaptedQueuePool) is correct.
            self.engine = create_async_engine(
                database_url,
                pool_size=settings.database_pool_size,
                max_overflow=settings.database_max_overflow,
                pool_timeout=settings.database_pool_timeout,
                pool_recycle=settings.database_pool_recycle,
                pool_pre_ping=True,
                echo=False,
            )
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            logger.info("Database connection pool initialized")

        # FIX 3: errors are no longer swallowed here. The old code logged and set
        # session_factory = None, which let callers silently fall back to fake data.

    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None

    def get_session(self) -> AsyncSession:
        # FIX 4: this was `async def`, so `async with db_pool.get_session()` received
        # a coroutine instead of a session and raised. A plain method returns the
        # AsyncSession, which is itself an async context manager.
        if not self.session_factory:
            raise RuntimeError("Database pool not initialized")
        return self.session_factory()


# Global database pool instance, shared by every request
db_pool = DatabasePool()


async def get_db_session():
    """Dependency to get a database session."""
    await db_pool.initialize()
    async with db_pool.get_session() as session:
        yield session