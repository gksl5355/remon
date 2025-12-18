#======================================================================
# app/ai_pipeline/nodes/generate_strategy.py
# 규제 대응 전략 생성 노드 (CoT 투명성 강화)
#
# [State 입출력 요약]
# --- INPUT (from AppState) ---
#   mapping: MappingResults
#   change_detection_results: List[Dict]     # 변경 감지 상세 결과
#   previous_regulation_summary: Optional[str] # 이전 규제 요약
#
# --- OUTPUT (to AppState) ---
#   strategies: List[Dict]                   # CoT 구조화된 전략 리스트
#       - previous_requirement: str
#       - current_requirement: str
#       - impact_reasoning: str (CoT)
#       - recommended_strategy: str
#
# [큰 흐름]
#   1) 변경 감지 결과 + 이전 규제 정보 조회
#   2) 현재 규제 요약 + 제품 ID 추출
#   3) HybridRetriever로 유사 규제-제품 이력 검색
#   4) CoT 프롬프트로 LLM 호출 (이전→현재→이유→전략)
#   5) JSON 파싱하여 구조화된 전략 반환
#   6) StrategyHistoryTool로 Qdrant에 저장
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

from app.ai_pipeline.prompts.strategy_prompt import STRATEGY_PROMPT

#----------------------------------------------------------------------
# 설정
#----------------------------------------------------------------------

STRATEGY_HISTORY_COLLECTION = os.getenv(
    "QDRANT_STRATEGY_COLLECTION",
    "skala-2.4.17-strategy",
)

# history 검색 시 가져올 최대 개수
HISTORY_TOP_K = 5


#----------------------------------------------------------------------
# 도구 인스턴스 (모듈 로드 시 1회 생성) - 원격 서버 사용
#----------------------------------------------------------------------

retriever = HybridRetriever(
    default_collection=STRATEGY_HISTORY_COLLECTION,
)

history_tool = StrategyHistoryTool(
    collection=STRATEGY_HISTORY_COLLECTION,
)


#----------------------------------------------------------------------
# 유틸: LLM 출력 -> 전략 리스트 파싱
#----------------------------------------------------------------------

def _parse_strategies(raw_text: str) -> List[Dict[str, str]]:
    """
    LLM이 생성한 JSON 텍스트에서 CoT 구조화된 전략 리스트 추출.

    처리 규칙:
    - 1차: JSON 파싱 (CoT 구조: previous_requirement, current_requirement, impact_reasoning, recommended_strategy)
    - 2차: Fallback - 기존 문자열 파싱 (하위 호환성)
    
    Returns:
        List[Dict[str, str]]: CoT 구조화된 전략 리스트
    """
    import json
    
    strategies: List[Dict[str, str]] = []
    
    # -------------------------------
    # 1차: JSON 파싱 (CoT 구조)
    # -------------------------------
    raw_stripped = raw_text.strip()
    if raw_stripped.startswith('{') or raw_stripped.startswith('[') or '```json' in raw_stripped:
        try:
            # 마크다운 코드 블록 제거
            json_text = raw_stripped
            if '```json' in json_text:
                start = json_text.find('```json') + 7
                end = json_text.find('```', start)
                if end > start:
                    json_text = json_text[start:end].strip()
            elif '```' in json_text:
                start = json_text.find('```') + 3
                end = json_text.find('```', start)
                if end > start:
                    json_text = json_text[start:end].strip()
            
            parsed = json.loads(json_text)
            
            # CoT 구조 파싱
            if isinstance(parsed, dict) and 'items' in parsed:
                for item in parsed['items']:
                    if isinstance(item, dict):
                        strategy = {
                            "regulation_change": item.get("regulation_change", item.get("change_summary", "")),
                            "product_context": item.get("product_context", item.get("current_product_status", "")),
                            "previous_strategy": item.get("previous_strategy", "없음"),
                            "recommended_strategy": item.get("recommended_strategy", item.get("summary", "")),
                            "rationale": item.get("rationale", item.get("strategy_reasoning", ""))
                        }
                        if strategy["recommended_strategy"]:
                            strategies.append(strategy)
                
                if strategies:
                    print(f"✅ CoT JSON 파싱 성공: {len(strategies)}개 전략 추출")
                    return strategies
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"⚠️ JSON 파싱 실패, Fallback 사용: {e}")
    
    # -------------------------------
    # 2차 Fallback: 기존 문자열 파싱 (하위 호환성)
    # -------------------------------
    numbered_list_pattern = re.compile(r"^[0-9]{1,2}[.)]\s+")
    text_strategies: List[str] = []
    
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        
        cleaned = line
        m = numbered_list_pattern.match(cleaned)
        if m:
            cleaned = cleaned[m.end():].strip()
        if cleaned and cleaned[0] in ("-", "•", "*"):
            cleaned = cleaned[1:].strip()
        
        if cleaned:
            text_strategies.append(cleaned)
    
    # 문자열을 CoT 구조로 변환 (Fallback)
    for text in text_strategies:
        strategies.append({
            "regulation_change": "(변경 감지 실패)",
            "product_context": "(알 수 없음)",
            "previous_strategy": "없음",
            "recommended_strategy": text,
            "rationale": "(근거 없음)"
        })
    
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
    current_regulation_summary: str,
    change_analysis: str,
    products: List[str],
    history_strategies: List[str],
) -> str:

    products_block = (
        "\n".join(f"- {p}" for p in products) 
        if products else "- (no mapped products)"
    )
    history_block = (
        "\n".join(f"- {s}" for s in history_strategies)
        if history_strategies
        else "- (no relevant historical strategies)"
    )

    prompt = STRATEGY_PROMPT.format(
        current_regulation_summary=current_regulation_summary,
        change_analysis=change_analysis,
        products_block=products_block,
        history_block=history_block,
    )

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

async def generate_strategy_node(state: AppState) -> Dict[str, Any]:
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

    if mapping_results is None:
        raise ValueError(
            "state.mapping 이 비어 있습니다. "
            "map_products 노드 결과가 필요합니다."
        )
    
    items = mapping_results["items"]

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
    product_info = state.get("product_info") or {}
    product_name = product_info.get("product_name") if isinstance(product_info, dict) else None
    mapped_products = [product_name] if product_name else []

    # 2) history 검색 (HybridRetriever) - SSL 오류 시 graceful fallback
    query_text = _build_query_text(regulation_summary, mapped_products)
    history_results = []

    try:
        history_tool.ensure_collection()
        history_results = retriever.search(
            query=query_text,
            limit=HISTORY_TOP_K,
        )
        print(f"✅ History 검색 성공: {len(history_results)}개 결과")
    except Exception as exc:
        print(f"⚠️ History 검색 실패 (무시하고 계속): {exc}")
        history_results = []
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

    # 3) regulation_id 조회
    regulation_id = None
    regulation = state.get("regulation", {})
    if regulation:
        regulation_id = regulation.get("regulation_id")
    
    if not regulation_id:
        preprocess_results = state.get("preprocess_results", [])
        if preprocess_results:
            regulation_id = preprocess_results[0].get("regulation_id")
    
    # 4) 변경 감지 결과 조회 및 분석 텍스트 생성
    change_detection_results = state.get("change_detection_results", [])
    change_analysis = ""
    
    if change_detection_results:
        change_lines = []
        for idx, change in enumerate(change_detection_results[:5], 1):  # 최대 5개만
            section = change.get("section", "Unknown")
            change_type = change.get("change_type", "Unknown")
            summary = change.get("summary", "")
            change_lines.append(f"{idx}. [{section}] {change_type}: {summary}")
        change_analysis = "\n".join(change_lines)
        print(f"✅ 변경 감지 결과 활용: {len(change_detection_results)}개 변경사항")
    else:
        change_analysis = "(변경 감지 결과 없음 - 신규 규제 또는 변경 감지 실패)"
        print("⚠️ 변경 감지 결과 없음")
    
    # 5) LLM 호출하여 새로운 대응 전략 생성 (CoT 구조)
    refined_prompt = state.get("refined_generate_strategy_prompt")

    if refined_prompt:
        print("[Strategy] Using REFINED STRATEGY PROMPT from validator")
        
        products_block = (
            "\n".join(f"- {p}" for p in mapped_products) 
            if mapped_products else "- (no mapped products)"
        )
        history_block = (
            "\n".join(f"- {s}" for s in history_strategies)
            if history_strategies
            else "- (no relevant historical strategies)"
        )
        
        try:
            temp_prompt = refined_prompt
            # Placeholder 임시 치환
            temp_prompt = temp_prompt.replace("{current_regulation_summary}", "__CURR_REG__")
            temp_prompt = temp_prompt.replace("{change_analysis}", "__CHANGE__")
            temp_prompt = temp_prompt.replace("{products_block}", "__PRODUCTS__")
            temp_prompt = temp_prompt.replace("{history_block}", "__HISTORY__")
            
            # 중괄호 이스케이프
            temp_prompt = temp_prompt.replace("{", "{{").replace("}", "}}")
            
            # Placeholder 복원
            temp_prompt = temp_prompt.replace("__CURR_REG__", "{current_regulation_summary}")
            temp_prompt = temp_prompt.replace("__CHANGE__", "{change_analysis}")
            temp_prompt = temp_prompt.replace("__PRODUCTS__", "{products_block}")
            temp_prompt = temp_prompt.replace("__HISTORY__", "{history_block}")
            
            prompt = temp_prompt.format(
                current_regulation_summary=regulation_summary,
                change_analysis=change_analysis,
                products_block=products_block,
                history_block=history_block,
            )
            
            print(f"[Strategy] ✅ Refined prompt 적용 완료: {len(prompt)} chars")
        except KeyError as e:
            print(f"⚠️ Refined prompt format 실패: {e}, 기본 프롬프트 사용")
            prompt = _build_llm_prompt(
                current_regulation_summary=regulation_summary,
                change_analysis=change_analysis,
                products=mapped_products,
                history_strategies=history_strategies,
            )
    else:
        prompt = _build_llm_prompt(
            current_regulation_summary=regulation_summary,
            change_analysis=change_analysis,
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

    # 🔍 전략 생성 결과 출력 (CoT 구조)
    print("\n" + "="*80)
    print("📋 [전략 생성 완료 - CoT 구조]")
    print("="*80)
    for idx, strategy in enumerate(new_strategies, 1):
        print(f"\n전략 {idx}:")
        print(f"  [변경 규제] {strategy.get('regulation_change', 'N/A')}")
        print(f"  [제품 관련내용] {strategy.get('product_context', 'N/A')}")
        print(f"  [기존 적용 전략] {strategy.get('previous_strategy', 'N/A')}")
        print(f"  [새롭게 제안되는 전략] {strategy.get('recommended_strategy', 'N/A')}")
        print(f"  [근거] {strategy.get('rationale', 'N/A')}")
    print("\n" + "="*80 + "\n")

    # refined prompt 성공 후 제거
    if state.get("refined_generate_strategy_prompt"):
        state["refined_generate_strategy_prompt"] = None
        print("✅ HITL refined prompt 적용 완료 (제거됨)")

    # 6) Qdrant history 저장 (실패해도 파이프라인은 계속 진행)
    try:
        # CoT 구조에서 recommended_strategy만 추출하여 저장
        strategy_texts = [s.get("recommended_strategy", "") for s in new_strategies if s.get("recommended_strategy")]
        history_tool.save_strategy_history(
            regulation_summary=regulation_summary,
            mapped_products=mapped_products,
            strategies=strategy_texts,
        )
    except Exception as e:
        print(f"[generate_strategy_node] history 저장 중 예외 발생: {e}")

    # LangGraph 에서는 이 dict 이 AppState 에 merge 됨
    # (state["strategies"]: List[str])
    state["strategies"] = new_strategies
    
    # 🆕 중간 결과물 저장 (HITL용)
    regulation_id = None
    regulation = state.get("regulation", {})
    if regulation:
        regulation_id = regulation.get("regulation_id")
    
    if not regulation_id:
        preprocess_results = state.get("preprocess_results", [])
        if preprocess_results:
            regulation_id = preprocess_results[0].get("regulation_id")
    
    if regulation_id and new_strategies:
        from app.core.repositories.intermediate_output_repository import IntermediateOutputRepository
        from app.core.database import AsyncSessionLocal
        
        print(f"💾 전략 중간 결과물 저장 시작: regulation_id={regulation_id}")
        
        async with AsyncSessionLocal() as session:
            intermediate_repo = IntermediateOutputRepository()
            try:
                intermediate_data = {
                    "strategies": new_strategies,
                    "regulation_summary": regulation_summary,
                    "change_analysis": change_analysis,
                    "mapped_products": mapped_products,
                    "history_strategies_used": history_strategies,
                }
                await intermediate_repo.save_intermediate(
                    session,
                    regulation_id=regulation_id,
                    node_name="generate_strategy",
                    data=intermediate_data
                )
                await session.commit()
                print(f"✅ 전략 중간 결과물 저장 완료: regulation_id={regulation_id}")
            except Exception as db_err:
                await session.rollback()
                print(f"❌ 전략 중간 결과물 저장 실패: {db_err}")
    else:
        print(f"⚠️ 전략 중간 결과물 저장 스킵: regulation_id={regulation_id}, strategies={len(new_strategies) if new_strategies else 0}")
    
    return state

 