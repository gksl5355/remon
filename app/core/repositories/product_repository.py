from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.models import Product, ProductExportCountry, Country
from app.core.models.enums import ProductCategoryEnum
from .base_repository import BaseRepository

class ProductRepository(BaseRepository[Product]):
    def __init__(self):
        super().__init__(Product)
    
    async def get_by_category(
        self, db: AsyncSession, category: ProductCategoryEnum
    ) -> List[Product]:
        """카테고리별 제품 조회"""
        result = await db.execute(
            select(Product).where(Product.product_category == category)
        )
        return result.scalars().all()
    
    async def get_export_countries(
        self, db: AsyncSession, product_id: int
    ) -> List[Country]:
        """제품의 수출 국가 목록 조회"""
        result = await db.execute(
            select(Country)
            .join(ProductExportCountry)
            .where(ProductExportCountry.product_id == product_id)
        )
        return result.scalars().all()
    
    async def get_with_export_countries(
        self, db: AsyncSession, product_id: int
    ) -> Optional[Product]:
        """수출 국가 정보를 포함한 제품 조회"""
        result = await db.execute(
            select(Product)
            .options(selectinload(Product.export_countries))
            .where(Product.product_id == product_id)
        )
        return result.scalar_one_or_none()
