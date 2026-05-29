from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from .config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.execute(__import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # Idempotent schema migrations for columns added after initial release
        for ddl in [
            "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS page_number INTEGER",
            "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS context TEXT",
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary TEXT",
        ]:
            await conn.execute(__import__("sqlalchemy").text(ddl))
