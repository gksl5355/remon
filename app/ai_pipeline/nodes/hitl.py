# app/ai_pipeline/nodes/hitl.py
"""
HITL(Human-In-The-Loop) 통합 노드

기능:
1) intent 분류 (question/modification)
2) question: 답변만 제공 (파이프라인 재실행 없음)
3) modification: target_node 식별 + 피드백 정제 + 파이프라인 재실행
4) DB 중간 결과물 활용
5) LangGraph 내 report 이후에 위치하는 hitl 노드
"""

import os
import json
import logging
import re
from typing import Dict, Any
from datetime import datetime

from openai import OpenAI
from app.ai_pipeline.state import AppState

# Import prompts for refined prompt generation
from app.ai_pipeline.prompts.mapping_prompt import MAPPING_PROMPT, MAPPING_SCHEMA
from app.ai_pipeline.prompts.strategy_prompt import STRATEGY_PROMPT, STRATEGY_SCHEMA
from app.ai_pipeline.prompts.impact_prompt import IMPACT_PROMPT, IMPACT_SCHEMA
from app.ai_pipeline.prompts.refined_prompt import REFINED_PROMPT

logger = logging.getLogger(__name__)
client = OpenAI()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ============================================================
# 1) Intent Classification (Question vs Modification)
# ============================================================

INTENT_CLASSIFICATION_PROMPT = """
당신은 REMON의 Intent 분류기입니다.

사용자 입력을 2가지로 분류하십시오:

1. **question**: 결과에 대한 질문/설명 요청
   - 예시: "이 결과가 뭐야?", "왜 이렇게 나왔어?", "영향도가 뭔데?"
   - 예시: "이 매핑은 어떻게 된 거야?", "전략이 이해가 안 돼"
   - 예시: "변경 감지가 뭐야?", "이 점수는 어떻게 계산된 거야?"

2. **modification**: 파이프라인 수정 요청
   - 예시: "매핑을 고쳐줘", "영향도를 낮춰줘", "전략을 다시 만들어줘"
   - 예시: "변경 감지를 다시 해줘", "제품을 바꿔줘", "다시 분석해줘"

출력(JSON):
{
  "intent": "question" | "modification",
  "confidence": 0.0~1.0,
  "reasoning": "분류 이유 (한글)"
}
"""

def classify_intent(message: str) -> Dict[str, Any]:
    """사용자 메시지 → intent 분류 (question/modification)"""
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": INTENT_CLASSIFICATION_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        
        result = json.loads(raw)
        return {
            "intent": result.get("intent", "question"),
            "confidence": result.get("confidence", 0.5),
            "reasoning": result.get("reasoning", "")
        }
    except Exception as e:
        logger.warning(f"Intent 분류 실패: {e}, 기본값 question 사용")
        return {"intent": "question", "confidence": 0.0, "reasoning": "parsing_error"}


# ============================================================
# 2) Question Answering (파이프라인 재실행 없음)
# ============================================================

async def answer_question(state: AppState, question: str) -> str:
    """
    사용자 질문에 대한 답변 생성 (파이프라인 재실행 없음)
    
    DB와 state에서 컨텍스트를 수집하여 LLM으로 답변 생성
    """
    context_parts = []
    
    # 1) 규제 정보
    regulation = state.get("regulation", {})
    if regulation:
        context_parts.append(f"규제명: {regulation.get('title', 'N/A')}")
        context_parts.append(f"국가: {regulation.get('country', 'N/A')}")
        context_parts.append(f"인용 코드: {regulation.get('citation_code', 'N/A')}")
    
    # 2) 변경 감지 결과
    change_summary = state.get("change_summary", {})
    if change_summary:
        total = change_summary.get("total_changes", 0)
        high_conf = change_summary.get("high_confidence_changes", 0)
        context_parts.append(f"변경 감지: 총 {total}개 변경 (고신뢰도 {high_conf}개)")
    
    change_results = state.get("change_detection_results", [])
    if change_results:
        context_parts.append("\n주요 변경 사항:")
        for idx, result in enumerate(change_results[:3], 1):
            if result.get("change_detected"):
                section = result.get("section_ref", 'Unknown')
                change_type = result.get("change_type", 'N/A')
                context_parts.append(f"  {idx}. {section}: {change_type}")
    
    # 3) 매핑 결과
    mapping = state.get("mapping", {})
    if mapping:
        items = mapping.get("items", [])
        product_name = mapping.get("product_name", "Unknown")
        context_parts.append(f"\n매핑 결과 ({product_name}): {len(items)}개 항목")
        
        # 주요 매핑 항목 (applies=True만, 최대 5개)
        applies_items = [item for item in items if item.get("applies")]
        for idx, item in enumerate(applies_items[:5], 1):
            feature = item.get("feature_name", 'N/A')
            current = item.get("current_value", '-')
            required = item.get("required_value", '-')
            context_parts.append(f"  {idx}. {feature}: {current} → {required}")
    
    # 4) 영향도
    impact_scores = state.get("impact_scores", [])
    if impact_scores:
        impact = impact_scores[0]
        level = impact.get("impact_level", 'N/A')
        score = impact.get("weighted_score", 0.0)
        reasoning = impact.get("reasoning", '')[:200]
        context_parts.append(f"\n영향도: {level} (점수: {score:.2f})")
        if reasoning:
            context_parts.append(f"근거: {reasoning}...")
    
    # 5) 전략
    strategies = state.get("strategies", [])
    if strategies:
        context_parts.append(f"\n대응 전략:")
        for idx, strategy in enumerate(strategies[:3], 1):
            context_parts.append(f"  {idx}. {strategy[:150]}...")
    
    context = "\n".join(context_parts)
    
    # LLM 답변 생성
    prompt = f"""당신은 REMON 규제 분석 시스템의 설명 전문가입니다.

사용자 질문에 대해 아래 컨텍스트를 기반으로 명확하고 간결하게 답변하세요.

**컨텍스트**:
{context}

**사용자 질문**:
{question}

**답변 규칙**:
1. 한글로 답변 (고유명사, 수치, 법령 조항, 국가 코드는 원문 유지)
2. 3-5문장으로 간결하게
3. 컨텍스트에 없는 내용은 "해당 정보가 분석 결과에 포함되지 않았습니다"라고 명시
4. 전문 용어는 쉽게 풀어서 설명
5. 구체적인 수치와 예시를 포함
"""
    
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "당신은 규제 분석 결과를 쉽게 설명하는 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )
        answer = resp.choices[0].message.content.strip()
        logger.info(f"✅ 질문 답변 생성 완료: {len(answer)} chars")
        return answer
    except Exception as e:
        logger.error(f"❌ 질문 답변 생성 실패: {e}")
        return "죄송합니다. 답변 생성 중 오류가 발생했습니다. 다시 시도해주세요."


# ============================================================
# 3) Target Node Detection (Modification용)
# ============================================================

TARGET_NODE_PROMPT = """
당신은 REMON의 HITL target_node 분류기입니다.

사용자 메시지에서 수정하려는 파이프라인 단계를 식별하십시오:

- change_detection: 변경 감지 관련
- map_products: 제품 매핑 관련  
- generate_strategy: 전략 생성 관련
- score_impact: 영향도 점수 관련

출력(JSON):
{
  "target_node": "change_detection" | "map_products" | "generate_strategy" | "score_impact"
}
"""

def detect_target_node(message: str) -> str:
    """사용자 메시지 → target_node"""
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": TARGET_NODE_PROMPT},
            {"role": "user", "content": message},
        ],
        temperature=0,
    )
    raw = resp.choices[0].message.content.strip()

    try:
        result = json.loads(raw)
        return result.get("target_node", "map_products")
    except Exception:
        return "map_products"


# ============================================================
# 2) Feedback Cleaning
# ============================================================

CHANGE_FEEDBACK_PROMPT = """
사용자의 메시지가 의미하는 변경 감지 결과를 판단하십시오.

반드시 아래 JSON 형식으로만 답하십시오:

{ "manual_change": true }   ← 변경 있음으로 처리
또는
{ "manual_change": false }  ← 변경 없음으로 처리
"""

IMPACT_LEVEL_FEEDBACK_PROMPT = """
사용자의 피드백을 분석해서 원하는 영향도 레벨을 판단하십시오.

사용자가 원하는 것:
- 낮추고 싶다면: Low
- 높이고 싶다면: High  
- 보통/적당히/조금만 수정하고 싶다면: Medium

반드시 아래 JSON 형식으로만 답하십시오:

{ "desired_level": "Low" | "Medium" | "High" }
"""

STRATEGY_STYLE_FEEDBACK_PROMPT = """
사용자의 피드백을 분석해서 원하는 전략 스타일을 판단하십시오.

사용자가 원하는 것:
- 보수적/안전하게/신중하게: conservative
- 적극적/공격적/빠르게: aggressive
- 단계적/점진적/차근차근: gradual
- 간단하게/핵심만/최소한: minimal
- 자세하게/많이/구체적으로: detailed

반드시 아래 JSON 형식으로만 답하십시오:

{ "strategy_style": "conservative" | "aggressive" | "gradual" | "minimal" | "detailed" | "default" }
"""

def refine_hitl_feedback(message: str, target_node: str) -> str:
    """
    노드 타입에 따라 피드백 정제

    - change_detection: "true" / "false" 문자열로 정제
    - score_impact: "Low" / "Medium" / "High" 레벨로 정제
    - 나머지 노드: 자연어 피드백 한 문장 그대로 사용
    """

    if target_node == "change_detection":
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": CHANGE_FEEDBACK_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        try:
            data = json.loads(raw)
            flag = bool(data.get("manual_change", False))
            return "true" if flag else "false"
        except Exception:
            return "false"
    
    elif target_node == "score_impact":
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": IMPACT_LEVEL_FEEDBACK_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        try:
            data = json.loads(raw)
            return data.get("desired_level", "Medium")
        except Exception:
            return "Medium"
    
    elif target_node == "generate_strategy":
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": STRATEGY_STYLE_FEEDBACK_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        try:
            data = json.loads(raw)
            return data.get("strategy_style", "default")
        except Exception:
            return "default"

    # map_products → 그냥 자연어 사용
    return message.strip()


# ============================================================
# 3) Apply HITL → Patch State + call validator
# ============================================================

def generate_refined_prompt(node_name: str, pipeline_state: dict, error_summary: str):
    """Generate a refined version of the original prompt for a specific node."""
    
    if node_name == "map_products":
        original_prompt = MAPPING_PROMPT
        schema = MAPPING_SCHEMA
    elif node_name == "generate_strategy":
        original_prompt = STRATEGY_PROMPT
        schema = STRATEGY_SCHEMA
    elif node_name == "score_impact":
        original_prompt = IMPACT_PROMPT
        schema = IMPACT_SCHEMA
        # score_impact 전용: 숫자 출력 강제
        error_summary += "\n\nCRITICAL REQUIREMENT: All score values MUST be plain NUMBERS (1-5), NOT objects or nested structures.\n" + \
                        "CORRECT: 'directness': 3, 'legal_severity': 4\n" + \
                        "WRONG: 'directness': {'score': 3}, 'directness': {'value': 3, 'reason': '...'}\n" + \
                        "OUTPUT ONLY FLAT JSON with number values. NO nested objects allowed."
    else:
        logger.error(f"[HITL] Unknown node for refinement: {node_name}")
        return None

    # 🆕 중간 결과물 추가 컨텍스트
    intermediate_context = ""
    intermediate_data = pipeline_state.get("intermediate_data")
    if intermediate_data:
        if node_name == "change_detection" and "change_detection" in intermediate_data:
            prev_data = intermediate_data["change_detection"]
            intermediate_context = f"\n\n[PREVIOUS CHANGE DETECTION RESULTS]\n"
            intermediate_context += f"Total changes detected: {len(prev_data.get('change_detection_results', []))}\n"
            intermediate_context += f"Summary: {prev_data.get('change_summary', {})}\n"
        elif node_name == "map_products" and "map_products" in intermediate_data:
            prev_data = intermediate_data["map_products"]
            intermediate_context = f"\n\n[PREVIOUS MAPPING RESULTS]\n"
            intermediate_context += f"Total items: {len(prev_data.get('mapping', {}).get('items', []))}\n"
            intermediate_context += f"Product: {prev_data.get('product_info', {}).get('product_name', 'Unknown')}\n"
    
    error_summary += intermediate_context

    # score_impact는 간단한 override 프롬프트 사용
    if node_name == "score_impact" and "Force impact_level to" in error_summary:
        # 직접 override 프롬프트 생성 (REFINED_PROMPT 우회)
        refine_request = f"""{error_summary}

Original Prompt:
{original_prompt.strip()}

You MUST include the exact phrase "Force impact_level to 'High'" (or Low/Medium) in your rewritten prompt.
This phrase is used for automated detection.

Rewrite the prompt to enforce the human override while maintaining the original structure.
"""
    else:
        refine_request = REFINED_PROMPT.format(
            original_prompt=original_prompt.strip(),
            error_summary=error_summary,
            pipeline_state=json.dumps(pipeline_state, ensure_ascii=False, indent=2),
            schema=json.dumps(schema, ensure_ascii=False, indent=2),
        )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You rewrite prompts to be strict and error-proof.",
                },
                {"role": "user", "content": refine_request},
            ],
            temperature=0,
        )
        refined_prompt_text = resp.choices[0].message.content.strip()
        return refined_prompt_text

    except Exception as e:
        logger.error(f"[HITL] Failed to generate refined prompt: {e}")
        return None


async def apply_hitl_patch(state: AppState, target_node: str, cleaned_feedback: str) -> AppState:
    """
    HITL 피드백을 독립적으로 처리 (validator 의존성 제거)
    + DB에서 중간 결과물 로드 및 재활용
    """
    
    logger.info(f"[HITL] Processing feedback for {target_node}: {cleaned_feedback}")
    
    # 🆕 DB에서 중간 결과물 로드
    regulation_id = state.get("regulation", {}).get("regulation_id")
    intermediate_data = None
    
    if regulation_id:
        from app.core.repositories.intermediate_output_repository import IntermediateOutputRepository
        from app.core.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            intermediate_repo = IntermediateOutputRepository()
            try:
                intermediate_data = await intermediate_repo.get_intermediate(
                    session,
                    regulation_id=regulation_id
                )
                if intermediate_data:
                    logger.info(f"✅ 중간 결과물 로드 성공: regulation_id={regulation_id}")
                    logger.info(f"   노드: {list(intermediate_data.keys())}")
            except Exception as db_err:
                logger.error(f"❌ 중간 결과물 로드 실패: {db_err}")
    
    # compiled_input에 DB 데이터 병합
    compiled_input = {
        "mapping": state.get("mapping"),
        "strategies": state.get("strategies"),
        "impact": state.get("impact_scores"),
        "regulation": state.get("regulation"),
        "intermediate_data": intermediate_data,  # 🆕 DB 데이터 추가
    }
    
    # ===============================
    # change_detection 전용 HITL
    # ===============================
    if target_node == "change_detection":
        # 문자열("true"/"false") 처리
        if isinstance(cleaned_feedback, str):
            cleaned = cleaned_feedback.strip().lower()
            manual_flag = cleaned == "true"
        else:
            manual_flag = bool(cleaned_feedback)

        state["manual_change_flag"] = manual_flag
        state["needs_embedding"] = manual_flag

        logger.info(
            f"[HITL][change_detection] "
            f"manual_change_flag set to {manual_flag}, needs_embedding={manual_flag}"
        )

        if not manual_flag:  # 변경 없음일 때 - change_detection.py와 동일한 로직
            # change_detection.py와 동일한 "변경 없음" 상태 설정
            state["change_detection_results"] = []
            state["change_summary"] = {
                "status": "manual_no_change",
                "total_changes": 0,
                "high_confidence_changes": 0,
                "total_reference_blocks": 0,
            }
            state["change_detection_index"] = {}
            state["regulation_analysis_hints"] = {}
            
            logger.info("[HITL][change_detection] 변경 없음 상태 직접 설정 완료 (재실행 불필요)")
            # 재실행 불필요 - 이미 완료된 상태로 설정
        else:
            # 변경 있음일 때만 초기화 후 재실행
            for key in [
                "change_detection_results",
                "change_summary",
                "regulation_analysis_hints",
                "change_detection_index",
            ]:
                if key in state:
                    state[key] = None

            state["restarted_node"] = "change_detection"
            logger.info("[HITL][change_detection] 변경 있음 - 재실행 설정")
        
    # ===============================
    # 나머지 노드들 HITL
    # ===============================
    else:
        # 모든 노드에 대해 error_summary 생성
        if target_node == "score_impact":
            desired_level = cleaned_feedback
            error_summary = (
                f"**CRITICAL OVERRIDE INSTRUCTION**\n\n"
                f"MANDATORY: Force impact_level to '{desired_level}' and reasoning to 'Human in the loop'.\n\n"
                f"This is a HUMAN-IN-THE-LOOP correction. You MUST:\n"
                f"1. Set impact_level = '{desired_level}' (ignore calculated scores)\n"
                f"2. Set reasoning = 'Human in the loop'\n"
                f"3. All raw_scores must be plain numbers (1-5), NOT objects\n\n"
                f"Example CORRECT output:\n"
                f"{{\n"
                f"  \"directness\": 3,\n"
                f"  \"legal_severity\": 4,\n"
                f"  \"reasoning\": \"Human in the loop\"\n"
                f"}}\n"
            )
            logger.info(f"[HITL] Processing score_impact feedback: {desired_level}")
        else:
            error_summary = f"HUMAN FEEDBACK: {cleaned_feedback}. INSTRUCTION: Adjust the analysis according to this feedback."

        # 노드별 관련 state 초기화 (누적 방지)
        if target_node == "generate_strategy":
            state["strategies"] = None
            logger.info(f"[HITL] Cleared existing strategies for regeneration")
        elif target_node == "map_products":
            state["mapping"] = None
            state["product_info"] = None
            logger.info(f"[HITL] Cleared existing mapping and product_info for regeneration")
        elif target_node == "score_impact":
            state["impact_scores"] = None
            logger.info(f"[HITL] Cleared existing impact scores for regeneration")
        
        # refined prompt 생성
        refined_key = f"refined_{target_node}_prompt"
        try:
            refined_prompt = generate_refined_prompt(
                node_name=target_node,
                pipeline_state=compiled_input,
                error_summary=error_summary,
            )

            if refined_prompt:
                state[refined_key] = refined_prompt
                logger.info(f"[HITL] ✅ Refined prompt 생성 성공: {refined_key}")
                logger.info(f"[HITL] 프롬프트 내용: {refined_prompt[:300]}...")
            else:
                logger.error(f"[HITL] ❌ Refined prompt 생성 실패: {target_node}")
        except Exception as e:
            logger.error(f"[HITL] ❌ Refined prompt 생성 예외: {target_node}: {e}")

        # 재시작 노드 설정
        state["restarted_node"] = target_node
        logger.info(f"[HITL] Set restart node to: {target_node}")
    
    # 🆕 중간 결과물을 state에 복원 (재실행 시 활용)
    if intermediate_data and target_node in ["change_detection", "map_products"]:
        node_data = intermediate_data.get(target_node)
        if node_data:
            if target_node == "change_detection":
                # 변경 감지 결과 복원 (참고용)
                state["_hitl_previous_change_detection"] = node_data
                logger.info("✅ 이전 변경 감지 결과 복원 (참고용)")
            elif target_node == "map_products":
                # 매핑 결과 복원 (참고용)
                state["_hitl_previous_mapping"] = node_data
                logger.info("✅ 이전 매핑 결과 복원 (참고용)")
    
    # HITL 메타데이터 초기화
    state["hitl_target_node"] = None
    state["hitl_feedback_text"] = None
    state.pop("hitl_feedback", None)
    
    return state


# ============================================================
# 4) LangGraph HITL 노드 (report 이후)
# ============================================================

async def hitl_node(state: AppState) -> AppState:
    """
    LangGraph에서 report 이후 호출되는 HITL 노드.
    
    Intent 분류:
    - question: 답변만 제공 (파이프라인 재실행 없음)
    - modification: 파이프라인 재실행
    
    DB에서 중간 결과물 로드 및 재활용
    """
    
    user_msg = state.get("external_hitl_feedback")
    
    if not user_msg:
        logger.info("[HITL Node] external_hitl_feedback 없음 → 종료")
        return state
    
    logger.info(f"[HITL Node] 사용자 입력 수신: {user_msg}")
    
    # 피드백 제거 (무한 루프 방지)
    state["external_hitl_feedback"] = None
    
    # 🆕 Intent 분류
    intent_result = classify_intent(user_msg)
    intent = intent_result["intent"]
    confidence = intent_result["confidence"]
    reasoning = intent_result["reasoning"]
    
    logger.info(
        f"[HITL Intent] {intent} (confidence: {confidence:.2f}) - {reasoning}"
    )
    
    # 🔹 Intent별 처리
    if intent == "question":
        # 질문 처리: 답변만 생성 (파이프라인 재실행 없음)
        logger.info("[HITL Question] 답변 생성 시작...")
        answer = await answer_question(state, user_msg)
        
        # 답변을 state에 저장 (프론트엔드에서 표시)
        state["hitl_answer"] = {
            "question": user_msg,
            "answer": answer,
            "intent": "question",
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"[HITL Question] 답변 생성 완료: {answer[:100]}...")
        
        # 재실행 없음
        state["restarted_node"] = None
        
    elif intent == "modification":
        # 수정 처리: 기존 로직 (파이프라인 재실행)
        logger.info("[HITL Modification] 파이프라인 수정 시작...")
        
        # (1) target_node 식별
        target = detect_target_node(user_msg)
        logger.info(f"[HITL Target] target_node = {target}")
        
        # (2) 피드백 정제
        cleaned = refine_hitl_feedback(user_msg, target)
        
        # 🔍 원본 메시지 저장 (디버깅용)
        state["_hitl_original_message"] = user_msg
        
        # (3) state 패치 (독립적 처리 + DB 로드)
        new_state = await apply_hitl_patch(state, target, cleaned)
        
        logger.info(
            f"[HITL Modification] 처리 완료 → "
            f"restarted_node={new_state.get('restarted_node')}"
        )
        
        return new_state
    
    return state
