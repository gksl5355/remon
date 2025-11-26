import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.models import Base, Regulation
from app.core.repositories.regulation_repository import RegulationRepository

@pytest.fixture
async def db_session():
    engine = create_async_engine("postgresql+asyncpg://test:test@localhost/test_db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_create_regulation(db_session):
    repo = RegulationRepository()
    data = {
        "source_id": 1,
        "country_code": "US",
        "title": "Test Regulation"
    }
    regulation = await repo.create(db_session, data)
    assert regulation.regulation_id is not None
    assert regulation.title == "Test Regulation"
