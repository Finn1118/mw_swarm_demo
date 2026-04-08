from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from swarm.config import settings

engine = create_async_engine(settings.postgres_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    from swarm.db.models import Base

    async with engine.begin() as conn:
        await conn.execute(sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    await engine.dispose()


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


import sqlalchemy  # noqa: E402 — needed for text() in init_db
