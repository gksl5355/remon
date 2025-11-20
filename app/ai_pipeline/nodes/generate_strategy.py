#======================================================================
# app/ai_pipeline/nodes/generate_strategy.py
# 규제 대응 전략 생성 노드
#
# [State 입출력 요약]
# --- INPUT (from AppState) ---
#   mapping: MappingResults
#       - product_id: str
#       - items: List[MappingItem]
#           - regulation_summary: str        # 규제 요약 텍스트
#           - ...                           # (기타 매핑 정보)
#
#   ※ map_products_node 가 state["mapping"] 에 채워주는 구조를 그대로 사용.
#
# --- OUTPUT (to AppState) ---
#   strategies: List[str]                    # 규제 기준 최종 대응 전략 문자열 리스트
#
# [큰 흐름]
#   1) map_products 결과에서 현재 규제 요약 + 제품 ID 추출
#   2) HybridRetriever 로 Qdrant history에서 유사 규제-제품 포인트 검색
#   3) payload.meta_strategies 기반으로 과거 대응 전략 리스트(history) 구성
#   4) 현재 규제 + 제품 + history 를 LLM 프롬프트에 넣어
#      새로운 대응 전략 리스트 생성
#   5) {"strategies": ...} 형태로 반환하여 state에 merge
#   6) StrategyHistoryTool 로 Qdrant history 에도 새 대응 전략 저장
#======================================================================

from __future__ import annotations

from typing import List, Dict, Any, Set
import os
import re
import textwrap

from app.ai_pipeline.state import AppState
from app.ai_pipeline.nodes.llm import llm
from app.ai_pipeline.tools.hybrid_retriever import HybridRetriever
from app.ai_pipeline.tools.strategy_history import StrategyHistoryTool  


#----------------------------------------------------------------------
# 설정
#----------------------------------------------------------------------

STRATEGY_HISTORY_COLLECTION = os.getenv(
    "QDRANT_STRATEGY_COLLECTION",
    "remon_strategy_history",
)
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# history 검색 시 가져올 최대 개수
HISTORY_TOP_K = 5


#----------------------------------------------------------------------
# 도구 인스턴스 (모듈 로드 시 1회 생성)
#----------------------------------------------------------------------

retriever = HybridRetriever(
    default_collection=STRATEGY_HISTORY_COLLECTION,
    host=QDRANT_HOST,
    port=QDRANT_PORT,
)

history_tool = StrategyHistoryTool(
    collection=STRATEGY_HISTORY_COLLECTION,
    host=QDRANT_HOST,
    port=QDRANT_PORT,
)


#----------------------------------------------------------------------
# 유틸: LLM 출력 -> 전략 리스트 파싱
#----------------------------------------------------------------------

def _parse_strategies(raw_text: str) -> List[str]:
    """
    LLM이 생성한 텍스트에서 대응 전략 문장 리스트만 추출하는 파서.

    처리 규칙:
    - 1차: '1.', '2)', '-', '•' 등으로 시작하는 라인의 번호/불릿만 제거하고 문장만 수집
      - 번호 리스트: 한 자리 또는 두 자리 숫자 + ('.' 또는 ')') + 공백 (예: "1. xxx", "2) xxx")
      - 불릿: "- xxx", "• xxx", "* xxx"
      - 날짜("2025-11-19")처럼 숫자+'-' 패턴은 건드리지 않음
    - 2차: 1차 파싱 결과가 비어 있으면,
      - 전체 출력에서 공백이 아닌 각 줄을 그대로 전략 한 줄로 간주하여 보존
      - 즉, 형식이 깨져도 내용 자체는 버리지 않고 최대한 살림
    """
    strategies: List[str] = []

    # 번호 리스트 패턴: "1. 내용", "2) 내용"
    numbered_list_pattern = re.compile(r"^[0-9]{1,2}[.)]\s+")

    # -------------------------------
    # 1차 파싱: 예상 형식 기반 파싱
    # -------------------------------
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue

        cleaned = line

        # 번호 리스트 ("1. 전략", "2) 전략") → 번호만 제거
        m = numbered_list_pattern.match(cleaned)
        if m:
            cleaned = cleaned[m.end():].strip()

        # 불릿 ("- 전략", "• 전략", "* 전략") → 불릿만 제거
        if cleaned and cleaned[0] in ("-", "•", "*"):
            cleaned = cleaned[1:].strip()

        if cleaned:
            strategies.append(cleaned)

    # -----------------------------------------
    # 2차 fallback: 형식이 완전 망가져도 내용은 살린다
    # -----------------------------------------
    if not strategies:
        for line in raw_text.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            strategies.append(cleaned)

    return strategies


#----------------------------------------------------------------------
# 유틸: 규제 + 제품 리스트 -> history 검색용 query 텍스트 구성
#----------------------------------------------------------------------

def _build_query_text(regulation_summary: str, products: List[str]) -> str:
    """
    history 검색용 기준 텍스트 생성.
    StrategyHistoryTool._build_embedding_text 와 동일한 포맷 유지.
    """
    products_block = (
        ", ".join(products)
        if products
        else "(no mapped products)"
    )

    return f"Regulation: {regulation_summary.strip()}\nProducts: {products_block}"


#----------------------------------------------------------------------
# 유틸: LLM 프롬프트 구성
#----------------------------------------------------------------------

def _build_llm_prompt(
    regulation_summary: str,
    products: List[str],
    history_strategies: List[str],
) -> str:

    products_block = "\n".join(f"- {p}" for p in products) if products else "- (no mapped products)"
    history_block = (
        "\n".join(f"- {s}" for s in history_strategies)
        if history_strategies
        else "- (no relevant historical strategies)"
    )

    prompt = f"""
You are a senior regulatory compliance strategy consultant
specializing in global tobacco and nicotine regulations.

Generate **actionable, product-specific compliance strategies**
based on the information below.

[REGULATION SUMMARY]
{regulation_summary.strip()}

[MAPPED PRODUCTS]
{products_block}

[REFERENCE: HISTORICAL STRATEGIES]
{history_block}

[REQUIREMENTS]
1. Provide strategies that are immediately executable actions  
   (e.g., "Establish a reformulation plan…", "Initiate inventory withdrawal…",  
   "Prepare updated packaging…").

2. Consider both compliance (legal) requirements and business impact mitigation.

3. Output format: **one strategy per line**  
   (no bullets or numbering needed by the LLM; the parser will handle extraction).

4. When the regulation contains explicit numerical values  
   (e.g., nicotine concentration %, tar mg, warning label area %,  
   allowed advertising period, maximum refill volume, etc.),  
   you must reflect those numbers **exactly as stated**.  
   - Do NOT invent new numbers, percentages, limits, or thresholds.  
   - If the regulation provides no numbers, do NOT introduce any.

5. Each strategy must describe a **concrete, actionable operational task**.  
   - Examples: update packaging/labeling, conduct additional testing,  
     execute inventory depletion, adjust product formulation,  
     update online/offline product descriptions.  
   - Avoid vague principles such as "enhance compliance" or  
     "improve internal processes." Every line must be an action  
     that a real operational team can immediately execute.

6. Use the [REFERENCE: HISTORICAL STRATEGIES] only when they are relevant.  
   - Do NOT include historical strategies that do not match the current regulation  
     or the mapped products.  
   - If proposing new strategies, they must be clearly grounded in  
     either (a) the current regulation + products, or  
     (b) patterns observed in the historical strategies.

Now generate the strategies.
"""
    return textwrap.dedent(prompt).strip()



#----------------------------------------------------------------------
# 유틸: history payload -> 과거 전략 리스트 추출
#----------------------------------------------------------------------

def _extract_history_strategies(results: List[Dict[str, Any]]) -> List[str]:
    """
    HybridRetriever.search() 결과의 payload 들에서
    meta_strategies 기반으로 과거 전략 문자열 리스트를 추출.
    - meta_has_strategy == True 이고
    - meta_strategies: List[str] 이 있는 케이스만 사용
    - 중복 제거
    """
    collected: List[str] = []
    seen: Set[str] = set()

    for r in results:
        payload = r.get("payload") or {}

        has_strategy = payload.get("meta_has_strategy")
        meta_strategies = payload.get("meta_strategies")

        if not has_strategy:
            continue
        if not isinstance(meta_strategies, list):
            continue

        for s in meta_strategies:
            if not isinstance(s, str):
                continue
            s_norm = s.strip()
            if not s_norm:
                continue
            if s_norm in seen:
                continue
            seen.add(s_norm)
            collected.append(s_norm)

    return collected


#----------------------------------------------------------------------
# 메인 노드 함수
#----------------------------------------------------------------------

def generate_strategy_node(state: AppState) -> Dict[str, Any]:
    """
    LangGraph node: generate_strategy

    1) map_products 결과에서 현재 규제 요약 + 제품 ID를 추출
    2) HybridRetriever 로 Qdrant history 에서 유사 규제-제품의 과거 전략 검색
    3) LLM 으로 새로운 대응 전략 생성
    4) {"strategies": ...} 형태로 반환하여 state에 merge
    5) StrategyHistoryTool 로 Qdrant history 에도 저장
    """
    # 1) 현재 규제 요약 + 제품 리스트 추출
    # AppState 구현에 따라 dict / 객체 둘 다 대응
    #   - 공식 필드: state["mapping"]
    #   - 레거시 호환: state["mapping_results"] (있다면 fallback)
    mapping_results = getattr(state, "mapping", None)
    if mapping_results is None and isinstance(state, dict):
        mapping_results = state.get("mapping") or state.get("mapping_results")

    if not mapping_results:
        raise ValueError(
            "state.mapping 이 비어 있습니다. "
            "map_products 노드 결과가 필요합니다."
        )
    
    items: List[Dict[str, Any]] = mapping_results.get("items") or []

    # 매핑 결과가 하나도 없는 경우: 파이프라인은 계속 진행하되, 전략은 빈 리스트로 반환
    if not items:
        print(
            "[generate_strategy_node] mapping.items 가 비어 있습니다. "
            "해당 product에 매핑된 규제가 없어 전략 생성을 건너뜁니다."
        )
        return {"strategies": []}


    # 현재 루프에서는 1개의 규제만 처리한다고 가정
    current_item = items[0]

    regulation_summary: str = (current_item.get("regulation_summary") or "").strip()
    if not regulation_summary:
        raise ValueError("MappingItem.regulation_summary 가 비어 있습니다.")

    # 제품 리스트: 현재 파이프라인은 단일 product 기준이므로 product_id 하나만 리스트로 사용
    product_id = mapping_results.get("product_id")
    mapped_products: List[str] = [product_id] if product_id else []

    # 2) history 검색 (HybridRetriever)
    query_text = _build_query_text(regulation_summary, mapped_products)

    # 히스토리 컬렉션이 없을 경우 자동 생성 (검색·저장 모두 동일 컬렉션 사용)
    try:
        history_tool.ensure_collection()
    except Exception as exc:
        print(f"[generate_strategy_node] history 컬렉션 준비 중 예외 발생: {exc}")

    history_results = retriever.search(
        query=query_text,
        limit=HISTORY_TOP_K,
    )
    # history_results 예:
    # [
    #   {
    #     "id": "...",
    #     "score": 0.83,
    #     "payload": {
    #        "meta_has_strategy": True,
    #        "meta_strategies": ["...", ...],
    #        ...
    #     }
    #   },
    #   ...
    # ]

    history_strategies = _extract_history_strategies(history_results)

    # 3) LLM 호출하여 새로운 대응 전략 생성
    prompt = _build_llm_prompt(
        regulation_summary=regulation_summary,
        products=mapped_products,
        history_strategies=history_strategies,
    )

    raw_output = llm.invoke(prompt)

    # llm 래퍼 형태에 따라 문자열/메시지 모두 대응
    if hasattr(raw_output, "content"):
        raw_output_text = str(raw_output.content)
    else:
        raw_output_text = str(raw_output)

    new_strategies = _parse_strategies(raw_output_text)

    # 4) Qdrant history 저장 (실패해도 파이프라인은 계속 진행)
    try:
        history_tool.save_strategy_history(
            regulation_summary=regulation_summary,
            mapped_products=mapped_products,
            strategies=new_strategies,
        )
    except Exception as e:
        print(f"[generate_strategy_node] history 저장 중 예외 발생: {e}")

    # LangGraph 에서는 이 dict 이 AppState 에 merge 됨
    # (state["strategies"]: List[str])
    return {"strategies": new_strategies}
