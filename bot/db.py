"""Database engine and session factory setup."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def build_engine(database_url: str):  # type: ignore[no-untyped-def]
    """Create an async SQLAlchemy engine from a database URL."""
    return create_async_engine(database_url, echo=False)


def build_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Return an async session factory bound to the given database URL."""
    engine = build_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(database_url: str) -> None:
    """Create all tables defined in bot.models (used in tests and dev init)."""
    from bot.models.base import Base  # local import to avoid circular deps at module load

    engine = build_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
