"""Async database session factory."""

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)


@event.listens_for(engine.sync_engine, "connect")
def _on_connect(dbapi_conn, connection_record):
    """Enable pgvector extension on each new connection (PostgreSQL only)."""
    # SQLite connections don't support CREATE EXTENSION
    if hasattr(dbapi_conn, "cursor"):
        try:
            cursor = dbapi_conn.cursor()
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            dbapi_conn.commit()
            cursor.close()
        except Exception:
            # Not PostgreSQL — ignore
            try:
                dbapi_conn.rollback()
            except Exception:
                pass


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
