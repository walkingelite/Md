"""Async SQLAlchemy session factory.

The engine is created lazily. Building it at import time would mean no module
in the package could be imported without a reachable database, which makes
pure-logic components (compliance gates, the simulation engine) untestable in
isolation and couples every import to deployment state.
"""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ai_bos.config import settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = str(settings.database_url)
        kwargs: dict[str, Any] = {"echo": not settings.is_production}
        # SQLite (used by the test suite) has no connection pool to size.
        if not url.startswith("sqlite"):
            kwargs |= {
                "pool_size": 20,
                "max_overflow": 10,
                "pool_timeout": 30,
                "pool_recycle": 1800,
            }
        _engine = create_async_engine(url, **kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def reset_engine() -> None:
    """Dispose the engine and clear caches. Used between test runs."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


class _LazySessionLocal:
    """Callable proxy so `AsyncSessionLocal()` keeps working at call sites
    without any of them triggering engine construction on import."""

    def __call__(self, *args: Any, **kwargs: Any) -> AsyncSession:
        return get_session_factory()(*args, **kwargs)


AsyncSessionLocal = _LazySessionLocal()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
