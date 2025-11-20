"""
map_products.py
HybridRetriever 기반 검색 + LLM 매핑 Node (FINAL PRODUCTION VERSION)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

try:
    from openai import AsyncOpenAI
except Exception:
    AsyncOpenAI = None

from app.ai_pipeline.state import (
    ProductInfo,
    RetrievedChunk,
    RetrievalResult,
    MappingItem,
    MappingParsed,
    MappingResults,
    AppState,
    MappingContext,
)

from app.ai_pipeline.prompts.mapping_prompt import MAPPING_PROMPT
from app.ai_pipeline.tools.hybrid_retriever import HybridRetriever
from app.config.settings import settings
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# -------------------------------------------------------------
# Product Repository (RDB → ProductInfo 직렬화)
# -------------------------------------------------------------

FEATURE_UNIT_MAP: Dict[str, str] = {
    "nicotin": "mg",
    "tarr": "mg",
    "battery": "mAh",
    "label_size": "mm^2",
}

BOOLEAN_FEATURES = {"menthol", "incense", "security_auth"}

DEFAULT_EXPORT_COUNTRY = "US"

PRODUCT_SELECT_BASE = """
SELECT
    p.product_id,
    p.product_name,
    p.product_category,
    p.nicotin,
    p.tarr,
    p.menthol,
    p.incense,
    p.battery,
    p.label_size,
    p.security_auth,
    COALESCE(pec.country_code, :default_country) AS export_country
FROM products p
LEFT JOIN product_export_countries pec
    ON pec.product_id = p.product_id
"""


class ProductRepository:
    """DB에서 제품을 읽어 ProductInfo로 직렬화"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def fetch_product(self, product_id: Optional[int]) -> ProductInfo:
        params = {"default_country": DEFAULT_EXPORT_COUNTRY}

        if product_id is not None:
            query = text(
                PRODUCT_SELECT_BASE + " WHERE p.product_id = :pid ORDER BY p.product_id LIMIT 1"
            )
            params["pid"] = product_id
        else:
            query = text(PRODUCT_SELECT_BASE + " ORDER BY p.product_id LIMIT 1")

        async with self._session_factory() as session:
            result = await session.execute(query, params)
            row = result.mappings().first()

        if not row:
            raise ValueError("제품 정보를 찾을 수 없습니다.")

        return self._serialize_product(dict(row))

    def _serialize_product(self, row: Dict[str, Any]) -> ProductInfo:
        features: Dict[str, Any] = {}
        feature_units: Dict[str, str] = {}

        for field, unit in FEATURE_UNIT_MAP.items():
            v = row.get(field)
            if v not in (None, ""):
                features[field] = v
                feature_units[field] = unit

        for field in BOOLEAN_FEATURES:
            v = row.get(field)
            if v is not None:
                features[field] = bool(v)
                feature_units[field] = "boolean"

        return {
            "product_id": str(row["product_id"]),
            "name": row.get("product_name"),
            "export_country": row.get("export_country") or DEFAULT_EXPORT_COUNTRY,
            "category": row.get("product_category"),
            "features": features,
            "feature_units": feature_units,
        }


# -------------------------------------------------------------
# HybridRetriever + LLM 매핑 Node
# -------------------------------------------------------------

class MappingNode:
    """
    🔥 HybridRetriever 기반 검색 통합 Node
    """

    def __init__(
        self,
        llm_client,
        top_k: int = 5,
        alpha: float = 0.7,
        product_repository: Optional[ProductRepository] = None,
    ):
        self.llm = llm_client
        self.top_k = top_k
        self.alpha = alpha

        DEFAULT_COLLECTION = "remon_regulations"

        # 🔥 Qdrant Hybrid Retriever 연결
        self.retriever = HybridRetriever(
            default_collection=DEFAULT_COLLECTION,
            host="localhost",
            port=6333,
        )

        self.product_repository = (
            product_repository or ProductRepository(AsyncSessionLocal)
        )

        self.debug_enabled = settings.MAPPING_DEBUG_ENABLED

    # -----------------------------------------------------
    # Hybrid 검색 wrapper
    # -----------------------------------------------------
    async def _run_search(
        self,
        product: ProductInfo,
        feature_name: str,
        feature_value: Any,
        feature_unit: Optional[str],
    ) -> RetrievalResult:

        product_id = product["product_id"]
        query = self._build_search_query(feature_name, feature_value, feature_unit)

        try:
            results = self.retriever.search(
                query=query,
                limit=self.top_k,
                dense_weight=self.alpha,
                sparse_weight=1 - self.alpha,
            )
        except Exception as exc:
            logger.warning("HybridRetriever 검색 실패: %s", exc)
            return RetrievalResult(
                product_id=product_id,
                feature_name=feature_name,
                feature_value=feature_value,
                feature_unit=feature_unit,
                candidates=[],
            )

        candidates: List[RetrievedChunk] = []
        for item in results:
            candidates.append(
                RetrievedChunk(
                    chunk_id=item["id"],
                    chunk_text=item["payload"].get("text", ""),
                    semantic_score=item["score"],
                    metadata=item["payload"],
                )
            )

        return RetrievalResult(
            product_id=product_id,
            feature_name=feature_name,
            feature_value=feature_value,
            feature_unit=feature_unit,
            candidates=candidates,
        )

    # -----------------------------------------------------
    # Prompt 생성
    # -----------------------------------------------------
    def _build_prompt(self, feature_name, feature_value, feature_unit, chunk_text):
        feature_dict = {
            "name": feature_name,
            "value": feature_value,
            "unit": feature_unit,
        }
        feature_json = json.dumps(feature_dict, ensure_ascii=False)
        return (
            MAPPING_PROMPT
            .replace("{feature}", feature_json)
            .replace("{chunk}", chunk_text)
        )

    def _build_search_query(self, feature_name, feature_value, feature_unit):
        parts = [str(feature_name)]
        if feature_value is not None:
            parts.append(str(feature_value))
        if feature_unit:
            parts.append(feature_unit)
        return " ".join(parts)

    # -----------------------------------------------------
    # LLM mapping
    # -----------------------------------------------------
    async def _call_llm(self, prompt: str) -> Dict:
        try:
            res = await self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
            )
            return json.loads(res.choices[0].message.content)
        except Exception:
            return {
                "applies": False,
                "required_value": None,
                "current_value": None,
                "gap": None,
                "parsed": {
                    "category": None,
                    "requirement_type": "other",
                    "condition": None,
                },
            }

    # -----------------------------------------------------
    # LangGraph Node entrypoint
    # -----------------------------------------------------
    async def run(self, state: AppState) -> AppState:

        product = state.get("product_info")
        if not product:
            product_id = state.get("mapping_filters", {}).get("product_id")
            product = await self.product_repository.fetch_product(
                int(product_id) if product_id else None
            )
            state["product_info"] = product

        features = product["features"]
        units = product["feature_units"]
        product_id = product["product_id"]

        mapping_results: List[MappingItem] = []

        for feature_name, value in features.items():
            unit = units.get(feature_name)

            retrieval = await self._run_search(
                product, feature_name, value, unit
            )

            for cand in retrieval["candidates"]:
                prompt = self._build_prompt(feature_name, value, unit, cand["chunk_text"])
                llm_out = await self._call_llm(prompt)
                parsed: MappingParsed = llm_out.get("parsed", {})

                mapping_results.append(
                    MappingItem(
                        product_id=product_id,
                        feature_name=feature_name,
                        applies=llm_out["applies"],
                        required_value=llm_out["required_value"],
                        current_value=llm_out["current_value"],
                        gap=llm_out["gap"],
                        regulation_chunk_id=cand["chunk_id"],
                        regulation_summary=cand["chunk_text"][:120],
                        regulation_meta=cand["metadata"],
                        parsed=parsed,
                    )
                )

        state["mapping"] = MappingResults(
            product_id=product_id,
            items=mapping_results,
        )
        return state


# -------------------------------------------------------------
# Factory wrapper
# -------------------------------------------------------------

# _DEFAULT_LLM_CLIENT = None
_DEFAULT_LLM_CLIENT = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL,
    http_client=httpx.AsyncClient(trust_env=False)
)
_DEFAULT_MAPPING_NODE = None


def _get_default_llm_client():
    global _DEFAULT_LLM_CLIENT
    if not _DEFAULT_LLM_CLIENT:
        if AsyncOpenAI is None:
            raise RuntimeError("openai 패키지 필요합니다.")
        _DEFAULT_LLM_CLIENT = AsyncOpenAI()
    return _DEFAULT_LLM_CLIENT


def _get_default_mapping_node():
    global _DEFAULT_MAPPING_NODE
    if not _DEFAULT_MAPPING_NODE:
        _DEFAULT_MAPPING_NODE = MappingNode(
            llm_client=_get_default_llm_client(),
            top_k=settings.MAPPING_TOP_K,
            alpha=settings.MAPPING_ALPHA,
        )
    return _DEFAULT_MAPPING_NODE


async def map_products_node(state: AppState) -> AppState:
    context: MappingContext = state.get("mapping_context", {}) or {}
    
    if context:
        return await MappingNode(
            llm_client=context.get("llm_client", _get_default_llm_client()),
            top_k=context.get("top_k", settings.MAPPING_TOP_K),
            alpha=context.get("alpha", settings.MAPPING_ALPHA),
        ).run(state)

    return await _get_default_mapping_node().run(state)


__all__ = ["MappingNode", "map_products_node"]
