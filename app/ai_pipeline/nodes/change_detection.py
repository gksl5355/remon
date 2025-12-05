"""
module: change_detection.py
description: 규제 변경 감지 노드 (Reference ID 기반, 전처리 후 임베딩 전)
author: AI Agent
created: 2025-01-18
updated: 2025-01-18 (Reference ID 최적화)
dependencies:
    - openai
    - app.vectorstore.vector_client
    - app.ai_pipeline.state
"""

import json
import logging
from typing import Dict, Any, List, Optional, Literal
from openai import AsyncOpenAI

from app.ai_pipeline.state import AppState
from app.vectorstore.vector_client import VectorClient

logger = logging.getLogger(__name__)


# ==================== System Prompts ====================
CHANGE_DETECTION_SYSTEM_PROMPT = """You are a regulatory change detection expert with Reference ID-based context awareness.

**CRITICAL INSTRUCTIONS:**

1. **Complete Recall**: 
   - 사소해 보이는 수치 변경(예: 18mg → 20mg)도 반드시 감지하십시오.
   - 단어 하나의 차이(예: '권고' → '의무', 'may' → 'shall')도 놓치지 마십시오.

2. **Context Preservation with Reference IDs**:
   - Reference ID를 활용하여 문서 계층 구조와 맥락을 파악하십시오.
   - 수치를 추출할 때는 반드시 적용 대상과 조건을 함께 명시하십시오.
   - Reference ID 형식: {regulation_id}-{section_ref}-P{page_num}

3. **Chain of Thought (4 Steps)**:
   Step 1: Reference ID 기반 맥락 파악 (문서 구조, 계층)
   Step 2: 핵심 용어 비교 (수치, 의무 표현, 조건절)
   Step 3: 의미 변화 평가 (실질적 영향도)
   Step 4: 최종 판단 (변경 유형, 신뢰도)

4. **Adversarial Validation**:
   - 자신의 판단을 반박하는 근거를 찾으십시오.
   - 최종 판단 시 반박 근거를 고려하여 confidence를 조정하십시오.

**OUTPUT FORMAT (JSON):**
{
  "change_detected": true/false,
  "confidence_score": 0.0-1.0,
  "change_type": "value_change" | "scope_change" | "new_clause" | "removed" | "wording_only",
  "legacy_snippet": "원문 발췌 (최대 200자)",
  "new_snippet": "원문 발췌 (최대 200자)",
  "reasoning": {
    "step1_context_analysis": "Reference ID 기반 맥락 분석...",
    "step2_term_comparison": "핵심 용어 비교...",
    "step3_semantic_evaluation": "의미 변화 평가...",
    "step4_final_judgment": "최종 판단..."
  },
  "adversarial_check": {
    "counter_argument": "...",
    "rebuttal": "...",
    "adjusted_confidence": 0.0-1.0
  },
  "keywords": ["keyword1", "keyword2"],
  "numerical_changes": [
    {
      "field": "필드명",
      "legacy_value": "이전 값",
      "new_value": "새 값",
      "context": "적용 맥락",
      "impact": "HIGH" | "MEDIUM" | "LOW"
    }
  ]
}
"""

SECTION_MATCHING_PROMPT = """Match new reference blocks with legacy reference blocks based on section numbers and keywords.

Return JSON array of matches:
{
  "matches": [
    {
      "new_section_ref": "1114.5(a)(3)",
      "legacy_section_ref": "1114.5(a)(3)",
      "match_confidence": 0.98
    }
  ]
}
"""


# ==================== Confidence Scorer ====================
class ConfidenceScorer:
    """신뢰도 점수 계산."""

    @staticmethod
    def adjust_confidence(result: Dict[str, Any]) -> float:
        base_confidence = result.get("confidence_score", 0.5)

        if "adversarial_check" in result:
            base_confidence = result["adversarial_check"].get(
                "adjusted_confidence", base_confidence
            )

        if result.get("numerical_changes"):
            base_confidence = min(base_confidence + 0.1, 1.0)

        return base_confidence

    @staticmethod
    def get_confidence_level(
        confidence: float,
    ) -> Literal["HIGH", "MEDIUM", "LOW", "UNCERTAIN"]:
        if confidence >= 0.9:
            return "HIGH"
        elif confidence >= 0.7:
            return "MEDIUM"
        elif confidence >= 0.5:
            return "LOW"
        else:
            return "UNCERTAIN"


# ==================== Change Detection Node ====================
class ChangeDetectionNode:
    """독립 변경 감지 노드 (Reference ID 기반)."""

    def __init__(
        self,
        llm_client: Optional[AsyncOpenAI] = None,
        vector_client: Optional[VectorClient] = None,
        model_name: str = "gpt-4o-mini",
    ):
        if llm_client:
            self.llm = llm_client
        else:
            from app.ai_pipeline.preprocess.config import PreprocessConfig

            client = AsyncOpenAI()
            self.llm = PreprocessConfig.wrap_openai_client(client)

        self.vector_client = vector_client or VectorClient()
        self.model_name = model_name
        self.confidence_scorer = ConfidenceScorer()

    async def run(self, state: AppState, db_session=None) -> AppState:
        """변경 감지 노드 실행 (Reference ID 기반)."""
        logger.info("=== Change Detection Node 시작 (Reference ID 기반) ===")
        print("=== Change Detection Node 시작 (Reference ID 기반) ===")
        change_context = state.get("change_context", {})
        if not change_context:
            logger.info("change_context 없음, 변경 감지 스킵")
            state["change_detection_results"] = []
            state["change_summary"] = {
                "status": "skipped",
                "reason": "no_change_context",
            }
            return state

        # DB 세션 확인
        if not db_session:
            logger.error("db_session 없음")
            state["change_detection_results"] = []
            state["change_summary"] = {
                "status": "error",
                "reason": "no_db_session",
            }
            return state

        # 신규 규제 ID
        new_regulation_id = change_context.get("new_regulation_id")
        print(f"new_regulation_id: {new_regulation_id}")
        if not new_regulation_id:
            logger.error("new_regulation_id 없음")
            state["change_detection_results"] = []
            state["change_summary"] = {
                "status": "error",
                "reason": "no_new_regulation_id",
            }
            return state

        # 신규 규제 DB에서 조회
        from app.core.repositories.regulation_repository import RegulationRepository
        repo = RegulationRepository()
        new_regul_data = await repo.get_regul_data(db_session, new_regulation_id)
        
        if not new_regul_data:
            logger.warning(f"신규 regul_data 없음: regulation_id={new_regulation_id}")
            state["change_detection_results"] = []
            state["change_summary"] = {"status": "error", "reason": "no_new_regul_data"}
            return state

        # 신규 Reference Blocks 추출
        new_ref_blocks = self._extract_reference_blocks(new_regul_data)


        # Legacy 규제 식별
        legacy_regulation_id = change_context.get("legacy_regulation_id")
        print(f"legacy_regulation_id: {legacy_regulation_id}")

        # Legacy Reference Blocks 조회 (직접 제공 또는 DB 검색)
        legacy_regul_data = change_context.get("legacy_regul_data")
        print(f"legacy_regul_data: {bool(legacy_regul_data)}")

        if legacy_regul_data:
            # JSON 직접 비교 모드: legacy_regul_data에서 추출
            logger.info("Legacy 데이터 직접 사용 (JSON 비교 모드)")
            print("Legacy 데이터 직접 사용 (JSON 비교 모드)")
            legacy_ref_blocks = self._extract_reference_blocks(legacy_regul_data)
            if not legacy_regulation_id:
                legacy_regulation_id = "LEGACY"
        else:
            # DB 검색 모드
            if not legacy_regulation_id:
                legacy_regulation_id = await self._find_legacy_regulation_db(
                    new_regul_data, db_session, new_regulation_id
                )
                print(f"legacy_regulation_id: {legacy_regulation_id}")
                if not legacy_regulation_id:
                    logger.info("완전히 새로운 규제로 처리")
                    print("완전히 새로운 규제로 처리")
                    state["change_detection_results"] = []
                    state["change_summary"] = {
                        "status": "new_regulation",
                        "total_changes": 0,
                    }
                    return state

            legacy_ref_blocks = await self._get_legacy_reference_blocks_db(
                legacy_regulation_id, db_session
            )
            if not legacy_ref_blocks:
                logger.warning(
                    f"Legacy Reference Blocks 조회 실패: {legacy_regulation_id}"
                )
                state["change_detection_results"] = []
                state["change_summary"] = {
                    "status": "error",
                    "reason": "legacy_not_found",
                }
                return state

        logger.info(
            f"Reference Blocks: 신규 {len(new_ref_blocks)}개, Legacy {len(legacy_ref_blocks)}개"
        )

        # CoT Step 1: Section 매칭 (LLM 1회 호출)
        matched_pairs = await self._match_reference_blocks(
            new_ref_blocks, legacy_ref_blocks
        )
        logger.info(f"Section 매칭 완료: {len(matched_pairs)}개 쌍")

        # CoT Step 2-4: 변경 감지 (매칭된 쌍마다 LLM 호출)
        detection_results = []
        for pair in matched_pairs:
            result = await self._detect_change_by_ref_id(
                pair, new_regulation_id, legacy_regulation_id
            )
            if result:
                detection_results.append(result)

        # 신뢰도 조정
        for result in detection_results:
            result["confidence_score"] = self.confidence_scorer.adjust_confidence(
                result
            )
            result["confidence_level"] = self.confidence_scorer.get_confidence_level(
                result["confidence_score"]
            )

        # 요약 생성
        total_changes = sum(1 for r in detection_results if r.get("change_detected"))
        high_confidence = sum(
            1 for r in detection_results if r.get("confidence_level") == "HIGH"
        )

        state["change_detection_results"] = detection_results
        state["change_summary"] = {
            "status": "completed",
            "total_reference_blocks": len(matched_pairs),
            "total_changes": total_changes,
            "high_confidence_changes": high_confidence,
            "legacy_regulation_id": legacy_regulation_id,
            "new_regulation_id": new_regulation_id,
        }

        logger.info(
            f"✅ 변경 감지 완료: {total_changes}개 변경 감지 (HIGH: {high_confidence})"
        )
        print("node 끝")

        return state

    def _extract_reference_blocks(
        self, regul_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """regul_data에서 reference_blocks 추출 (Vision Pipeline 구조 대응)."""
        ref_blocks = []
        chunks = regul_data.get("chunks", [])
        
        # Vision Pipeline 출력 구조
        vision_pages = regul_data.get("vision_extraction_result", [])
        
        for page in vision_pages:
            structure = page.get("structure", {})
            page_num = page.get("page_num", 0)
            markdown_content = structure.get("markdown_content", "")
            reference_blocks = structure.get("reference_blocks", [])
            
            # reference_blocks가 있으면 사용
            if reference_blocks:
                lines = markdown_content.splitlines()
                total_lines = len(lines)
                for ref in reference_blocks:
                    start = max(ref.get("start_line", 0), 0)
                    end = ref.get("end_line", total_lines) or total_lines
                    end = min(end, total_lines)
                    snippet = "\n".join(lines[start:end]) if lines else markdown_content
                    
                    ref_blocks.append({
                        "section_ref": ref.get("section_ref", ""),
                        "text": snippet,  # markdown_content에서 실제 텍스트 추출
                        "keywords": ref.get("keywords", []),
                        "page_num": page_num,
                        "start_line": start,
                        "end_line": end,
                        "hierarchy": [],  # 계층 정보 (필요시 추가)
                    })
            else:
                # reference_blocks가 없으면 페이지 전체를 하나의 블록으로
                ref_blocks.append({
                    "section_ref": f"Page {page_num}",
                    "text": markdown_content[:500],  # 처음 500자
                    "keywords": self._extract_keywords(markdown_content),
                    "page_num": page_num,
                    "start_line": 0,
                    "end_line": len(markdown_content.splitlines()),
                    "hierarchy": [],
                })
        
        return ref_blocks
    
    def _extract_keywords(self, text: str, max_keywords: int = 5) -> List[str]:
        """텍스트에서 키워드 추출 (간단한 토큰 기반)."""
        import re
        
        if not text:
            return []
        
        # 숫자 포함 단어 우선 (예: 20mg, § 1141.1)
        numeric_words = re.findall(r'\b\w*\d+\w*\b', text)
        
        # 대문자 시작 단어 (고유명사)
        capitalized = re.findall(r'\b[A-Z][a-z]+\b', text)
        
        # 결합 및 중복 제거
        keywords = list(dict.fromkeys(numeric_words[:3] + capitalized[:3]))
        
        return keywords[:max_keywords]

    async def _find_legacy_regulation_db(
        self, regul_data: Dict[str, Any], db_session, exclude_regulation_id: int = None
    ) -> Optional[int]:
        """DB에서 Legacy 규제 검색."""
        if not regul_data:
            return None

        title = regul_data.get("title", "")
        country = regul_data.get("jurisdiction_code", "")
        print(f"DB Legacy 검색: title={title}, country={country}")
        logger.info(
            f"DB Legacy 검색: title={title}, country={country}"
        )

        try:
            from app.core.repositories.regulation_repository import RegulationRepository

            repo = RegulationRepository()
            print("_find_legacy_regulation_db 실행")
            regulation = await repo.find_by_title_and_country(
                db_session, title, country, exclude_regulation_id
            )

            if regulation:
                logger.info(f"DB Legacy 발견: regulation_id={regulation.regulation_id}")
                print(f"DB Legacy 발견: regulation_id={regulation.regulation_id}")
                return regulation.regulation_id

            logger.info("DB Legacy 미발견")
            print("DB Legacy 미발견")
            return None

        except Exception as e:
            logger.error(f"DB Legacy 검색 실패: {e}")
            return None

        
    async def _get_legacy_reference_blocks_db(
        self, regulation_id: int, db_session
    ) -> List[Dict[str, Any]]:
        """DB에서 Legacy regul_data 조회 후 Reference Blocks 추출."""
        try:
            from app.core.repositories.regulation_repository import RegulationRepository

            repo = RegulationRepository()
            regul_data = await repo.get_regul_data(db_session, regulation_id)

            if not regul_data:
                logger.warning(f"regul_data 없음: regulation_id={regulation_id}")
                return []

            ref_blocks = self._extract_reference_blocks(regul_data)
            logger.info(f"DB Legacy Reference Blocks: {len(ref_blocks)}개")

            return ref_blocks

        except Exception as e:
            logger.error(f"DB Legacy 조회 실패: {e}")
            return []


    async def _match_reference_blocks(
        self, new_blocks: List[Dict[str, Any]], legacy_blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        CoT Step 1: 계층 구조 기반 정확 매칭 (밀림 현상 방지).
        
        전략:
        1. 계층 구조 완전 일치 (hierarchy 배열 비교)
        2. section_ref 일치 (fallback)
        3. 키워드 유사도 (fuzzy matching)
        """
        logger.info("계층 구조 기반 매칭 시작 (규칙 기반)")

        matched_pairs = []
        matched_legacy_indices = set()

        # 전략 1: 계층 구조 완전 일치
        for new_block in new_blocks:
            new_hierarchy = new_block.get("hierarchy", [])
            
            if not new_hierarchy:
                continue
            
            for idx, legacy_block in enumerate(legacy_blocks):
                if idx in matched_legacy_indices:
                    continue
                
                legacy_hierarchy = legacy_block.get("hierarchy", [])
                
                # 계층 구조 완전 일치
                if new_hierarchy == legacy_hierarchy:
                    matched_pairs.append(
                        {
                            "new_block": new_block,
                            "legacy_block": legacy_block,
                            "match_confidence": 1.0,
                            "match_reason": f"Exact hierarchy match: {' > '.join(new_hierarchy)}",
                        }
                    )
                    matched_legacy_indices.add(idx)
                    break
        
        # 전략 2: section_ref 일치 (fallback)
        for new_block in new_blocks:
            # 이미 매칭된 경우 스킵
            if any(p["new_block"] == new_block for p in matched_pairs):
                continue
            
            new_section = new_block["section_ref"]
            
            for idx, legacy_block in enumerate(legacy_blocks):
                if idx in matched_legacy_indices:
                    continue
                
                legacy_section = legacy_block["section_ref"]
                
                if new_section == legacy_section:
                    matched_pairs.append(
                        {
                            "new_block": new_block,
                            "legacy_block": legacy_block,
                            "match_confidence": 0.9,
                            "match_reason": f"Section ref match: {new_section}",
                        }
                    )
                    matched_legacy_indices.add(idx)
                    break
        
        # 전략 3: 키워드 유사도 (fuzzy matching)
        for new_block in new_blocks:
            if any(p["new_block"] == new_block for p in matched_pairs):
                continue
            
            new_keywords = set(new_block.get("keywords", []))
            
            if not new_keywords:
                continue
            
            best_match = None
            best_score = 0.0
            
            for idx, legacy_block in enumerate(legacy_blocks):
                if idx in matched_legacy_indices:
                    continue
                
                legacy_keywords = set(legacy_block.get("keywords", []))
                
                if not legacy_keywords:
                    continue
                
                # Jaccard 유사도
                intersection = len(new_keywords & legacy_keywords)
                union = len(new_keywords | legacy_keywords)
                score = intersection / union if union > 0 else 0.0
                
                if score > best_score and score >= 0.5:  # 임계값
                    best_score = score
                    best_match = (idx, legacy_block)
            
            if best_match:
                idx, legacy_block = best_match
                matched_pairs.append(
                    {
                        "new_block": new_block,
                        "legacy_block": legacy_block,
                        "match_confidence": best_score,
                        "match_reason": f"Keyword similarity: {best_score:.2f}",
                    }
                )
                matched_legacy_indices.add(idx)

        logger.info(
            f"매칭 완료: {len(matched_pairs)}개 쌍 "
            f"(정확: {sum(1 for p in matched_pairs if p['match_confidence'] == 1.0)}, "
            f"section: {sum(1 for p in matched_pairs if p['match_confidence'] == 0.9)}, "
            f"fuzzy: {sum(1 for p in matched_pairs if p['match_confidence'] < 0.9)})"
        )
        return matched_pairs

    async def _detect_change_by_ref_id(
        self, pair: Dict[str, Any], new_regulation_id: str, legacy_regulation_id: str
    ) -> Optional[Dict[str, Any]]:
        """CoT Step 2-4: Reference ID 기반 정밀 변경 감지 (Agentic)."""
        new_block = pair["new_block"]
        legacy_block = pair["legacy_block"]

        section_ref = new_block["section_ref"]
        new_text = new_block["text"]
        legacy_text = legacy_block["text"]

        # Reference ID 생성
        new_ref_id = (
            f"{new_regulation_id}-{section_ref}-P{new_block.get('page_num', 0)}"
        )
        legacy_ref_id = (
            f"{legacy_regulation_id}-{section_ref}-P{legacy_block.get('page_num', 0)}"
        )

        # LLM 호출 (ref_id 기반 정밀 비교)
        try:
            prompt = f"""Perform PRECISE comparison using Reference IDs for context-aware analysis.

**Reference IDs:**
- Legacy: {legacy_ref_id}
- New: {new_ref_id}

**Legacy Regulation (Section {section_ref}):**
{legacy_text}

**New Regulation (Section {section_ref}):**
{new_text}

**Task**: 
1. Use Reference IDs to understand document context and hierarchy
2. Detect ALL substantive changes (numerical, wording, scope)
3. Follow Chain of Thought (4 steps)
4. Apply Adversarial Validation
5. Extract numerical changes with full context
"""

            response = await self.llm.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": CHANGE_DETECTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            result = json.loads(response.choices[0].message.content)
            result["section_ref"] = section_ref
            result["new_ref_id"] = new_ref_id
            result["legacy_ref_id"] = legacy_ref_id

            return result

        except Exception as e:
            logger.error(f"LLM 호출 실패 (Section {section_ref}): {e}")
            return {
                "section_ref": section_ref,
                "new_ref_id": new_ref_id,
                "legacy_ref_id": legacy_ref_id,
                "change_detected": False,
                "confidence_score": 0.0,
                "error": str(e),
            }


# ==================== 노드 함수 ====================
_default_node: Optional[ChangeDetectionNode] = None


async def change_detection_node(state: AppState, db_session=None) -> AppState:
    global _default_node
    if _default_node is None:
        _default_node = ChangeDetectionNode()
    return await _default_node.run(state, db_session)


__all__ = ["ChangeDetectionNode", "change_detection_node", "ConfidenceScorer"]
