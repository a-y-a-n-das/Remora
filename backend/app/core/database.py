from contextlib import asynccontextmanager
import ssl
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import get_settings
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

engine = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None


def _clean_database_url(url: str) -> tuple[str, dict]:
    """Remove unsupported query parameters for asyncpg and return connect_args."""
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    # asyncpg doesn't support channel_binding or sslmode (uses ssl context instead)
    query_params.pop("channel_binding", None)
    sslmode = query_params.pop("sslmode", None)

    cleaned_query = urlencode(query_params, doseq=True)
    cleaned_url = urlunparse(parsed._replace(query=cleaned_query))

    # Build connect_args for asyncpg
    connect_args = {}
    if sslmode in (["require"], ["verify-full"], ["verify-ca"]):
        # Create SSL context for Neon
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_context

    return cleaned_url, connect_args


def init_database() -> None:
    global engine, async_session_maker
    settings = get_settings()
    if not settings.NEON_DATABASE_URL:
        return
    cleaned_url, connect_args = _clean_database_url(settings.NEON_DATABASE_URL)
    engine = create_async_engine(
        cleaned_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args=connect_args,
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