"""FastAPI dependency injection providers."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import async_session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
