import os
import sys

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from testcontainers.community.postgres import PostgresContainer
import alembic.config
import alembic.command

# Spin up a real Postgres + pgvector container for all tests
# Scope=session ensures it only starts once for the whole test run
@pytest.fixture(scope="session")
def postgres_container():
    # We must use the pgvector image to support the embeddings column
    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        yield postgres

@pytest.fixture(scope="session")
def db_url(postgres_container):
    # Get the async URL for the app code and Alembic (env.py runs async)
    sync_url = postgres_container.get_connection_url()
    async_url = sync_url.replace("postgresql+psycopg2", "postgresql+asyncpg")
    if async_url.startswith("postgresql://"):
        async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")

    # Run Alembic migrations
    alembic_cfg = alembic.config.Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", async_url)
    alembic.command.upgrade(alembic_cfg, "head")
    
    yield async_url

@pytest.fixture()
def engine(db_url):
    engine = create_async_engine(db_url, echo=False)
    yield engine
    engine.sync_engine.dispose()

@pytest_asyncio.fixture()
async def db_session(engine):
    """
    Yields an async session. For pure unit isolation, we could wrap this in a transaction 
    and rollback, but since we wipe or truncate between tests or just use unique IDs, 
    we'll provide the raw session.
    """
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    async with async_session() as session:
        # Truncate tables on setup to ensure clean state for the test
        await session.execute(
            __import__("sqlalchemy").text("TRUNCATE TABLE papers, authors, categories, ingest_runs CASCADE")
        )
        await session.commit()
        
        yield session
