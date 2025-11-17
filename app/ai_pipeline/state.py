"""
state.py
LangGraph 전역 State 스키마 정의 – Production Minimal Version
"""

from typing import Any, Dict, List, Optional, TypeDict


# ---------------------------------------------------------------------------
# 1) 제품 정보 – 모든 노드가 참조하는 전역 정보
# ---------------------------------------------------------------------------
class ProductInfo(TypeDict):
    product_id: str
    features: Dict[str, Any]  # 예: {"battery_capacity": 3000, "noise": 70}
    feature_units: Dict[str, str]  # 예: {"battery_capacity": "mAh", "noise": "dB"}


# ---------------------------------------------------------------------------
# 2) 검색 결과 – 검색 TOOL → 매핑 노드로 전달되는 데이터 구조
# ---------------------------------------------------------------------------
class RetrievedChunk(TypeDict):
    chunk_id: str
    chunk_text: str
    semantic_score: float
    metadata: Dict[str, Any]


class RetrievalResult(TypeDict):
    product_id: str
    feature_name: str
    feature_value: Any
    feature_unit: Optional[str]
    candidates: List[RetrievedChunk]


# ---------------------------------------------------------------------------
# 3) 매핑 결과 – 매핑 노드 → 전략 노드
# ---------------------------------------------------------------------------
class MappingParsed(TypeDict):
    category: Optional[str]
    requirement_type: Optional[str]  # "max" | "min" | "range" | "boolean" | "other"
    condition: Optional[str]


class MappingItem(TypeDict):
    product_id: str
    feature_name: str

    applies: bool
    required_value: Any
    current_value: Any
    gap: Any

    regulation_chunk_id: str
    regulation_summary: str
    regulation_meta: Dict[str, Any]

    parsed: MappingParsed


class MappingResults(TypeDict):
    product_id: str
    items: List[MappingItem]


# ---------------------------------------------------------------------------
# 4) 전략 결과 – 전략 노드 → 리포트 노드
# ---------------------------------------------------------------------------
class StrategyItem(TypeDict):
    feature_name: str
    regulation_chunk_id: str
    impact_level: str
    summary: str
    recommendation: str


class StrategyResults(TypeDict):
    product_id: str
    items: List[StrategyItem]


# ---------------------------------------------------------------------------
# 5) LangGraph 전체 전역 State (AppState)
#    → "딱 필요한 전역 key"만 정의한다.
#    → 나머지 모든 값은 Node 내부 local 변수로만 사용한다.
# ---------------------------------------------------------------------------
class AppState(TypeDict, total=False):
    product_info: ProductInfo
    retrieval: RetrievalResult
    mapping: MappingResults
    strategy: StrategyResults
