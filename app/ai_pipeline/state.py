"""
state.py
LangGraph 전역 State 스키마 정의 – Production Minimal Version
"""

from typing import Any, Dict, List, Optional, TypedDict, Literal

# ---------------------------------------------------------------------------
# 1) 제품 정보 – 모든 노드가 참조하는 전역 정보
# ---------------------------------------------------------------------------


class ProductMapping(TypedDict, total=False):
    """제품 현재 상태/목표 상태."""

    target: Dict[str, Any]
    present_state: Dict[str, Any]


class ProductInfo(TypedDict):
    product_id: str
    product_name: str
    mapping: ProductMapping
    feature_units: Dict[str, str]
    country: Optional[str]
    category: Optional[str]


# ---------------------------------------------------------------------------
# 2) 검색 결과 – 검색 TOOL → 매핑 노드로 전달되는 데이터 구조
# ---------------------------------------------------------------------------
class RetrievedChunk(TypedDict):
    chunk_id: str
    chunk_text: str
    semantic_score: float
    metadata: Dict[str, Any]


class RetrievalResult(TypedDict):
    product_id: str
    feature_name: str
    feature_value: Any
    feature_unit: Optional[str]
    candidates: List[RetrievedChunk]


# ---------------------------------------------------------------------------
# 3) 매핑 결과 – 매핑 노드 → 전략 노드
# ---------------------------------------------------------------------------
class MappingParsed(TypedDict):
    category: Optional[str]
    requirement_type: Optional[str]  # "max" | "min" | "range" | "boolean" | "other"
    condition: Optional[str]


class MappingItem(TypedDict):
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


class MappingResults(TypedDict):
    product_id: str
    items: List[MappingItem]
    targets: Dict[str, Dict[str, Any]]


class MappingDebugInfo(TypedDict, total=False):
    """매핑 결과 디버그 로그/파일 메타데이터."""

    snapshot_path: str
    total_items: int


# ---------------------------------------------------------------------------
# 4) 프리프로세스/매핑 구성요소 보조 스키마
# ---------------------------------------------------------------------------
class PreprocessRequest(TypedDict, total=False):
    """전처리 노드에 전달되는 입력 파라미터."""

    pdf_paths: List[str]
    skip_vectorstore: bool
    product_info: ProductInfo


class PreprocessSummary(TypedDict, total=False):
    status: Literal["completed", "partial", "skipped", "error"]
    processed_count: int
    succeeded: int
    failed: int
    reason: Optional[str]


class MappingContext(TypedDict, total=False):
    """파이프라인 실행 시 주입 가능한 매핑 노드 의존성."""

    llm_client: Any
    search_tool: Any
    top_k: Optional[int]
    alpha: Optional[float]
    max_candidates_per_doc: Optional[int]


# ---------------------------------------------------------------------------
# 5) 전략 결과 – 전략 노드 → 리포트 노드
# ---------------------------------------------------------------------------
class StrategyItem(TypedDict):
    feature_name: str
    regulation_chunk_id: str
    impact_level: str
    summary: str
    recommendation: str


class StrategyResults(TypedDict):
    product_id: str
    items: List[StrategyItem]


class ReportDraft(TypedDict, total=False):
    generated_at: str
    status: str
    sections: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# 6) 영향도 평가 결과 타입 정의
# ---------------------------------------------------------------------------
class ImpactScoreItem(TypedDict):
    raw_scores: Dict[str, Any]
    reasoning: str
    weighted_score: float
    impact_level: str


# ---------------------------------------------------------------------------
# 7) LangGraph 전체 전역 State (AppState)
#    → "딱 필요한 전역 key"만 정의한다.
#    → 나머지 모든 값은 Node 내부 local 변수로만 사용한다.
# ---------------------------------------------------------------------------
class AppState(TypedDict, total=False):
    preprocess_request: PreprocessRequest
    preprocess_results: List[Dict[str, Any]]
    preprocess_summary: PreprocessSummary
    product_info: ProductInfo
    retrieval: RetrievalResult
    mapping: MappingResults
    mapping_debug: MappingDebugInfo
    strategies: List[str]
    validation_strategy: bool
    mapping_context: MappingContext
    impact_scores: List[ImpactScoreItem]
    report: ReportDraft
    translation_id: Optional[int]
    change_id: Optional[int]

    # Vision-Centric Preprocessing Pipeline 필드
    vision_extraction_result: List[Dict[str, Any]]  # 페이지별 Vision LLM 추출 결과
    graph_data: Dict[str, Any]  # 지식 그래프 (엔티티 + 관계)
    dual_index_summary: Dict[str, Any]  # Qdrant + Graph 저장 요약

    # change detection
    change_context: Dict[str, Any]  # Legacy 규제 메타데이터 (legacy_regulation_id 포함)
    change_detection_results: List[Dict[str, Any]]  # 변경 감지 상세 결과
    change_summary: Dict[str, Any]  # 변경 감지 요약
    change_detection: Dict[str, Any]
