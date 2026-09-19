from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import get_settings

engine = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None


def init_database() -> None:
    global engine, async_session_maker
    settings = get_settings()
    if not settings.NEON_DATABASE_URL:
        return
    engine = create_async_engine(
        settings.NEON_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


async def close_database() -> None:
    global engine
    if engine:
        await engine.dispose()
        engine = None


@asynccontextmanager
async def get_db_session() -> AsyncSession:
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db() -> AsyncSession:
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()