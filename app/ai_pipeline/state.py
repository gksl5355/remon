"""Pipeline state definitions for LangGraph."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class AppState(BaseModel):
    """
    LangGraph 파이프라인 전체에서 공유되는 상태(State)
    각 노드 간 데이터 교환의 공통 스키마
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    # 1️⃣ 입력 (규제 데이터 및 메타정보)
    regulation_text: Optional[str] = Field(None, description="규제 원문 텍스트")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="국가, 시행일 등 메타데이터"
    )

    # 2️⃣ 전처리 결과
    normalized_text: Optional[str] = Field(None, description="정규화된 규제 텍스트")
    extracted_terms: Optional[List[str]] = Field(
        None, description="추출된 핵심 용어 리스트"
    )

    # 3️⃣ 매핑 결과
    mapped_products: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="map_products 노드가 생성한 product↔regulation 매핑 결과(JSON dump, 점수·메타 데이타포함)",
    )

    # 4️⃣ 영향도 분석 결과
    impact_scores: Optional[Dict[str, float]] = Field(
        None, description="제품별 영향도 점수 (product_id → score)"
    )

    # 5️⃣ 대응 전략
    generated_strategy: Optional[str] = Field(
        None, description="LLM 기반 생성된 대응 전략"
    )
    validation_strategy: Optional[bool] = Field(
        None, description="전략 유효성 검증 결과 (True=통과, False=재생성)"
    )

    # 6️⃣ 리포트 결과
    report_summary: Optional[str] = Field(None, description="최종 요약 리포트 텍스트")
    report_data: Optional[Dict[str, Any]] = Field(
        None, description="리포트 상세 데이터 구조"
    )

    # 7️⃣ RAG Retrieval 결과 (🆕)
    retrieved_contexts: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="RAG 검색 결과 (벡터 제외, 메타데이터 + 텍스트 + 점수)"
    )
    retrieval_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="검색 메타정보 (전략, 소요시간, 필터 등)"
    )
    
    # 8️⃣ 내부 관리용
    error_log: Optional[List[str]] = Field(
        default_factory=list, description="에러/경고 로그"
    )
    run_id: Optional[str] = Field(None, description="실행 식별용 UUID")
