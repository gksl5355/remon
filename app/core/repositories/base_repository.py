from typing import TypeVar, Generic, Type, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import DeclarativeBase

ModelType = TypeVar("ModelType", bound=DeclarativeBase)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    async def create(self, db: AsyncSession, obj_in: dict) -> ModelType:
        """Create new record"""
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj
    
    async def get(self, db: AsyncSession, id: int) -> Optional[ModelType]:
        """Get record by ID"""
        result = await db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_multi(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """Get multiple records"""
        result = await db.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()
    
    async def update(
        self, db: AsyncSession, id: int, obj_in: dict
    ) -> Optional[ModelType]:
        """Update record"""
        await db.execute(
            update(self.model).where(self.model.id == id).values(**obj_in)
        )
        await db.flush()
        return await self.get(db, id)
    
    async def delete(self, db: AsyncSession, id: int) -> bool:
        """Delete record"""
        result = await db.execute(
            delete(self.model).where(self.model.id == id)
        )
        await db.flush()
        return result.rowcount > 0
    
    async def exists(self, db: AsyncSession, id: int) -> bool:
        """Check if record exists"""
        result = await db.execute(
            select(self.model.id).where(self.model.id == id)
        )
        return result.scalar_one_or_none() is not None
