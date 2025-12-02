# app/core/repositories/product_repository.py
"""
제품 Repository
"""
from typing import Optional, Dict, Any, Set
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.models.product_model import Product
from .base_repository import BaseRepository


# ========================================
# 도메인 상수
# ========================================
# 새로운 스키마에 맞춰 특성과 단위를 재정의
FEATURE_UNIT_MAP: Dict[str, str] = {
    "nicotine": "mg",            # nicotin -> nicotine
    "tar": "mg",                 # tarr -> tar
    "label_size": "text",        # varchar(50)
    "images_size": "text",       # New
    "package": "text",           # New
    "certifying_agencies": "text", # New
    "revenue": "currency",       # New (Integer)
    "supply_partner": "text",    # New
}

# Boolean 타입 컬럼 목록 업데이트
BOOLEAN_FEATURES: Set[str] = {"menthol", "flavor"} # incense -> flavor

DEFAULT_EXPORT_COUNTRY: str = "US"

# Raw SQL 쿼리 (JOIN 제거 및 컬럼 최신화)
PRODUCT_SELECT_BASE = """
SELECT
    p.product_id,
    p.product_name,
    p.product_category,
    p.nicotine,
    p.tar,
    p.menthol,
    p.flavor,
    p.label_size,
    p.images_size,
    p.package,
    p.certifying_agencies,
    p.revenue,
    p.supply_partner,
    p.country_code
FROM products p
"""


class ProductRepository(BaseRepository[Product]):
    """
    제품 Repository
    
    책임:
    - 제품 CRUD
    - 복잡한 조인 쿼리 (현재는 단일 테이블로 간소화됨)
    - DB Row → State.ProductInfo 변환 (기술적 변환)
    - 제품 특성 직렬화
    """
    
    def __init__(self):
        super().__init__(Product)
    
    async def fetch_product_for_mapping(
        self,
        db: AsyncSession,
        product_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        매핑 노드용 제품 정보 조회 (State.ProductInfo 형식)
        
        Args:
            db: AsyncSession
            product_id: 제품 ID (None이면 첫 번째 제품)
        
        Returns:
            State.ProductInfo 형식 딕셔너리
        
        Raises:
            ValueError: 제품을 찾을 수 없을 때
        """
        # params는 이제 단순히 ID 바인딩용으로만 사용 (default_country 조인 불필요)
        params = {}
        
        if product_id is not None:
            query = text(
                PRODUCT_SELECT_BASE
                + " WHERE p.product_id = :pid ORDER BY p.product_id LIMIT 1"
            )
            params["pid"] = product_id
        else:
            query = text(PRODUCT_SELECT_BASE + " ORDER BY p.product_id LIMIT 1")
        
        # 읽기 전용 쿼리 실행
        result = await db.execute(query, params)
        row = result.mappings().first()
        
        if not row:
            raise ValueError(
                f"제품을 찾을 수 없습니다 (product_id={product_id or 'first'})"
            )
        
        # 기술적 변환: DB Row → State.ProductInfo
        return self._serialize_product(dict(row))
    
    def _serialize_product(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        기술적 변환: DB Row → State.ProductInfo
        
        Args:
            row: SQL 결과 Row
        
        Returns:
            State.ProductInfo 형식 딕셔너리
        """
        features: Dict[str, Any] = {}
        feature_units: Dict[str, str] = {}
        
        # 1. 단위가 있는 특성 처리
        for field, unit in FEATURE_UNIT_MAP.items():
            value = row.get(field)
            
            # None이거나 빈 문자열인 경우 스킵 (revenue가 0인 경우는 포함해야 하므로 주의)
            if value is None or value == "":
                continue

            # Decimal 등 JSON 직렬화가 어려운 값은 미리 float/int로 변환한다.
            if isinstance(value, Decimal):
                value = float(value)
            
            features[field] = value
            feature_units[field] = unit
        
        # 2. Boolean 특성 처리
        for field in BOOLEAN_FEATURES:
            value = row.get(field)
            if value is None:
                continue
            features[field] = bool(value)
            feature_units[field] = "boolean"
        
        # 3. State.ProductInfo 형식 반환
        # export_country 컬럼이 사라지고 country_code가 직접 존재함
        country_code = row.get("country_code")
        
        return {
            "product_id": str(row["product_id"]),
            "product_name": row.get("product_name") or "Unknown Product",
            "country": country_code or DEFAULT_EXPORT_COUNTRY,
            "category": row.get("product_category") or "Unknown",
            "mapping": {
                "target": {},
                "present_state": features,
            },
            "feature_units": feature_units,
        }

# # app/core/repositories/product_repository.py
# """
# 제품 Repository
# """
# from typing import Optional, Dict, Any, Set
# from decimal import Decimal
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import text

# from app.core.models.product_model import Product
# from .base_repository import BaseRepository


# # ========================================
# # 도메인 상수
# # ========================================
# FEATURE_UNIT_MAP: Dict[str, str] = {
#     "nicotin": "mg",
#     "tarr": "mg",
#     "battery": "mAh",
#     "label_size": "mm^2",
#     "image": "text",
# }

# BOOLEAN_FEATURES: Set[str] = {"menthol", "incense", "security_auth"}

# DEFAULT_EXPORT_COUNTRY: str = "US"

# # Raw SQL 쿼리
# PRODUCT_SELECT_BASE = """
# SELECT
#     p.product_id,
#     p.product_name,
#     p.product_category,
#     p.nicotin,
#     p.tarr,
#     p.menthol,
#     p.incense,
#     p.battery,
#     p.label_size,
#     p.security_auth,
#     p.image,
#     COALESCE(pec.country_code, :default_country) AS export_country
# FROM products p
# LEFT JOIN product_export_countries pec
#     ON pec.product_id = p.product_id
# """


# class ProductRepository(BaseRepository[Product]):
#     """
#     제품 Repository
    
#     책임:
#     - 제품 CRUD
#     - 복잡한 조인 쿼리
#     - DB Row → State.ProductInfo 변환 (기술적 변환)
#     - 제품 특성 직렬화
#     """
    
#     def __init__(self):
#         super().__init__(Product)
    
#     async def fetch_product_for_mapping(
#         self,
#         db: AsyncSession,
#         product_id: Optional[int] = None
#     ) -> Dict[str, Any]:
#         """
#         매핑 노드용 제품 정보 조회 (State.ProductInfo 형식)
        
#         Args:
#             db: AsyncSession
#             product_id: 제품 ID (None이면 첫 번째 제품)
        
#         Returns:
#             State.ProductInfo 형식 딕셔너리
#             {
#                 "product_id": "123",
#                 "product_name": "제품명",
#                 "mapping": {
#                     "target": {...},
#                     "present_state": {"nicotin": 3.0, "battery": 3000},
#                 },
#                 "feature_units": {"nicotin": "mg", "battery": "mAh"}
#             }
        
#         Raises:
#             ValueError: 제품을 찾을 수 없을 때
#         """
#         # 복잡한 조인 쿼리 (Repository 책임)
#         params = {"default_country": DEFAULT_EXPORT_COUNTRY}
        
#         if product_id is not None:
#             query = text(
#                 PRODUCT_SELECT_BASE
#                 + " WHERE p.product_id = :pid ORDER BY p.product_id LIMIT 1"
#             )
#             params["pid"] = product_id
#         else:
#             query = text(PRODUCT_SELECT_BASE + " ORDER BY p.product_id LIMIT 1")
        
#         # 읽기 전용 쿼리 실행
#         result = await db.execute(query, params)
#         row = result.mappings().first()
        
#         if not row:
#             raise ValueError(
#                 f"제품을 찾을 수 없습니다 (product_id={product_id or 'first'})"
#             )
        
#         # 기술적 변환: DB Row → State.ProductInfo
#         return self._serialize_product(dict(row))
    
#     def _serialize_product(self, row: Dict[str, Any]) -> Dict[str, Any]:
#         """
#         기술적 변환: DB Row → State.ProductInfo
        
#         Args:
#             row: SQL 결과 Row
        
#         Returns:
#             State.ProductInfo 형식 딕셔너리
#         """
#         features: Dict[str, Any] = {}
#         feature_units: Dict[str, str] = {}
        
#         # 1. 단위가 있는 특성 처리
#         for field, unit in FEATURE_UNIT_MAP.items():
#             value = row.get(field)
#             if value in (None, ""):
#                 continue

#             # Decimal 등 JSON 직렬화가 어려운 값은 미리 float로 변환한다.
#             if isinstance(value, Decimal):
#                 value = float(value)

#             features[field] = value
#             feature_units[field] = unit
        
#         # 2. Boolean 특성 처리
#         for field in BOOLEAN_FEATURES:
#             value = row.get(field)
#             if value is None:
#                 continue
#             features[field] = bool(value)
#             feature_units[field] = "boolean"
        
#         # 3. State.ProductInfo 형식 반환
#         return {
#             "product_id": str(row["product_id"]),
#             "product_name": row.get("product_name") or "Unknown Product",
#             "country": row.get("export_country") or DEFAULT_EXPORT_COUNTRY,
#             "category": row.get("product_category") or "Unknown",
#             "mapping": {
#                 "target": {},
#                 "present_state": features,
#             },
#             "feature_units": feature_units,
#         }
