"""
module: change_detection.py
description: 규제 변경 감지 노드 (Reference ID 기반, 전처리 후 임베딩 전)
author: AI Agent
created: 2025-01-18
updated: 2025-01-21 (중복 run() 메서드 통합, 신규 규제 분석 로직 추가)
dependencies:
    - openai
    - app.vectorstore.vector_client
    - app.ai_pipeline.state
"""

import json
import logging
from typing import Dict, Any, List, Optional, Literal, Set
from openai import AsyncOpenAI

from app.ai_pipeline.state import AppState
from app.vectorstore.vector_client import VectorClient

logger = logging.getLogger(__name__)


# ==================== System Prompts ====================
CHANGE_DETECTION_SYSTEM_PROMPT = """You are a regulatory change detection expert with Reference ID-based context awareness.

**CRITICAL INSTRUCTIONS:**

1. **Complete Recall**: 
   - 사소해 보이는 수치 변경(예: 값 A → 값 B)도 반드시 감지하십시오. 단, 반드시 제공된 텍스트 내에 존재하는 수치만 추출해야 합니다.
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

NEW_REGULATION_ANALYSIS_PROMPT = """You are a regulatory compliance expert analyzing a NEW regulation.

**TASK:**
Extract key requirements and identify affected product areas for compliance mapping.

**INSTRUCTIONS:**
1. Summarize the regulation's main purpose (1-2 sentences)
2. Extract ALL key requirements:
   - Numerical limits (e.g., "nicotine ≤ 20mg/ml")
   - Mandatory features (e.g., "child-resistant packaging")
   - Prohibited substances
   - Labeling requirements
   - Testing/certification requirements
3. Identify affected product areas using normalized names:
   - Use snake_case (e.g., "nicotine_content", "package_volume")
   - Be specific (e.g., "warning_label_size" not just "labeling")

**OUTPUT FORMAT (JSON):**
{
  "regulation_summary": "Brief 1-2 sentence summary",
  "key_requirements": [
    {
      "requirement": "Descriptive name",
      "value": "Specific value or limit",
      "unit": "Unit if applicable (or null)",
      "context": "When/where this applies"
    }
  ],
  "affected_areas": ["snake_case_area_1", "snake_case_area_2"]
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
        model_name: Optional[str] = None,
    ):
        from app.ai_pipeline.preprocess.config import PreprocessConfig

        if llm_client:
            self.llm = llm_client
        else:
            client = AsyncOpenAI()
            self.llm = PreprocessConfig.wrap_openai_client(client)

        self.vector_client = vector_client or VectorClient()
        self.model_name = model_name or PreprocessConfig.CHANGE_DETECTION_MODEL
        self.confidence_scorer = ConfidenceScorer()

    async def run(self, state: AppState, db_session=None) -> AppState:
        """변경 감지 노드 실행 (짧은 DB 세션 사용)."""
        logger.info("=== Change Detection Node 시작 (Reference ID 기반) ===")
        change_context = state.get("change_context", {})
        if not change_context:
            logger.info("change_context 없음, 변경 감지 스킵")
            state["change_detection_results"] = []
            state["change_summary"] = {
                "status": "skipped",
                "reason": "no_change_context",
            }
            return state

        new_regulation_id = change_context.get("new_regulation_id")

        # 우선순위: 1) change_context.new_regul_data 2) preprocess_results[0] 3) DB
        new_regul_data = change_context.get("new_regul_data")
        if not new_regul_data:
            pre_results = state.get("preprocess_results") or []
            if pre_results:
                new_regul_data = pre_results[0]
                if not new_regulation_id:
                    new_regulation_id = (
                        new_regul_data.get("regulation_id")
                        or new_regul_data.get("regulation", {}).get("regulation_id")
                        or "INLINE_NEW"
                    )

        legacy_regulation_id = change_context.get("legacy_regulation_id")
        legacy_regul_data = change_context.get("legacy_regul_data")

        # DB가 필요한 경우에만 세션을 연다
        if not new_regul_data or (not legacy_regul_data and legacy_regulation_id):
            from app.core.repositories.regulation_repository import RegulationRepository
            from app.core.database import AsyncSessionLocal

            repo = RegulationRepository()
            async with AsyncSessionLocal() as session:
                if not new_regul_data:
                    if not new_regulation_id:
                        logger.error("new_regulation_id 없음")
                        state["change_detection_results"] = []
                        state["change_summary"] = {
                            "status": "error",
                            "reason": "no_new_regulation_id",
                        }
                        return state

                    new_regul_data = await repo.get_regul_data(
                        session, new_regulation_id
                    )
                    if not new_regul_data:
                        logger.warning(
                            f"신규 regul_data 없음: regulation_id={new_regulation_id}"
                        )
                        state["change_detection_results"] = []
                        state["change_summary"] = {
                            "status": "error",
                            "reason": "no_new_regul_data",
                        }
                        return state

                if not legacy_regul_data:
                    if not legacy_regulation_id:
                        legacy_regulation_id = await self._find_legacy_regulation_db(
                            new_regul_data, session, new_regulation_id
                        )
                        if not legacy_regulation_id:
                            logger.info(
                                "✅ 완전히 새로운 규제 (Legacy 없음) - 신규 분석 실행"
                            )

                            # 신규 규제 분석 (LLM)
                            analysis_hints = await self._analyze_new_regulation(
                                new_regul_data
                            )
                            state["regulation_analysis_hints"] = analysis_hints
                            logger.info(
                                f"✅ 신규 규제 분석 완료: {len(analysis_hints.get('key_requirements', []))}개 요구사항"
                            )
                            logger.info(
                                f"   affected_areas: {analysis_hints.get('affected_areas', [])}"
                            )

                            state["change_detection_results"] = []
                            state["change_summary"] = {
                                "status": "new_regulation",
                                "total_changes": 0,
                            }
                            state["needs_embedding"] = True
                            return state

                    legacy_regul_data = await repo.get_regul_data(
                        session, legacy_regulation_id
                    )
                    if not legacy_regul_data:
                        logger.warning(
                            f"Legacy regul_data 없음: regulation_id={legacy_regulation_id}"
                        )
                        state["change_detection_results"] = []
                        state["change_summary"] = {
                            "status": "error",
                            "reason": "legacy_not_found",
                        }
                        return state
                # end session block

        # legacy_regulation_id 없지만 legacy_regul_data 주입된 경우 기본값 세팅
        if legacy_regul_data and not legacy_regulation_id:
            legacy_regulation_id = (
                legacy_regul_data.get("regulation_id")
                or legacy_regul_data.get("regulation", {}).get("regulation_id")
                or "LEGACY"
            )
        # new_regulation_id 없을 때도 기본값 세팅
        if not new_regulation_id:
            new_regulation_id = (
                new_regul_data.get("regulation_id")
                or new_regul_data.get("regulation", {}).get("regulation_id")
                or "INLINE_NEW"
            )

        # ========== Reference Blocks 추출 (세션 불필요) ==========
        new_ref_blocks = self._extract_reference_blocks(new_regul_data)
        legacy_ref_blocks = self._extract_reference_blocks(legacy_regul_data)

        logger.info(
            f"Reference Blocks: 신규 {len(new_ref_blocks)}개, Legacy {len(legacy_ref_blocks)}개"
        )

        # ========== Section 매칭 (세션 불필요) ==========
        matched_pairs = await self._match_reference_blocks(
            new_ref_blocks, legacy_ref_blocks
        )
        logger.info(f"Section 매칭 완료: {len(matched_pairs)}개 쌍")

        # ========== LLM 변경 감지 (병렬 처리, 10개 단위) ==========
        import asyncio

        semaphore = asyncio.Semaphore(10)  # LangSmith 부하 방지

        async def detect_single_pair(pair):
            async with semaphore:
                return await self._detect_change_by_ref_id(
                    pair, new_regulation_id, legacy_regulation_id
                )

        logger.info(
            f"🔄 변경 감지 병렬 처리: {len(matched_pairs)}개 섹션 (10개 동시 제한)"
        )

        detection_results_raw = await asyncio.gather(
            *[detect_single_pair(pair) for pair in matched_pairs],
            return_exceptions=True,
        )

        detection_results = []
        for result in detection_results_raw:
            if isinstance(result, Exception):
                logger.error(f"❌ 변경 감지 실패: {result}")
                continue
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

        total_changes = sum(1 for r in detection_results if r.get("change_detected"))
        high_confidence = sum(
            1 for r in detection_results if r.get("confidence_level") == "HIGH"
        )

        # 상세 로그 출력
        logger.info("\n" + "=" * 80)
        logger.info("📋 변경 감지 상세 결과")
        logger.info("=" * 80)
        for idx, result in enumerate(detection_results, 1):
            section = result.get("section_ref", "Unknown")
            detected = result.get("change_detected", False)
            confidence = result.get("confidence_level", "UNKNOWN")
            change_type = result.get("change_type", "N/A")

            logger.info(f"\n[{idx}] Section: {section}")
            logger.info(f"  변경 감지: {detected}")
            logger.info(
                f"  신뢰도: {confidence} ({result.get('confidence_score', 0):.2f})"
            )
            logger.info(f"  변경 유형: {change_type}")

            if detected:
                logger.info(f"  Legacy: {result.get('legacy_snippet', '')[:100]}...")
                logger.info(f"  New: {result.get('new_snippet', '')[:100]}...")

                numerical = result.get("numerical_changes", [])
                if numerical:
                    logger.info(f"  수치 변경: {len(numerical)}개")
                    for num_change in numerical[:3]:
                        logger.info(
                            f"    - {num_change.get('field')}: {num_change.get('legacy_value')} → {num_change.get('new_value')}"
                        )

        logger.info("\n" + "=" * 80)

        state["change_detection_results"] = detection_results
        state["change_summary"] = {
            "status": "completed",
            "total_reference_blocks": len(matched_pairs),
            "total_changes": total_changes,
            "high_confidence_changes": high_confidence,
            "legacy_regulation_id": legacy_regulation_id,
            "new_regulation_id": new_regulation_id,
        }

        # 🔑 Section 기반 빠른 조회를 위한 인덱스 생성
        change_index = {}
        for result in detection_results:
            section = self._normalize_section_ref(result.get("section_ref", ""))
            if section and result.get("change_detected"):
                change_index[section] = result
        state["change_detection_index"] = change_index
        logger.info(f"📚 Change Index 생성: {len(change_index)}개 섹션")

        logger.info(
            f"✅ 변경 감지 완료: {total_changes}개 변경 감지 (HIGH: {high_confidence})"
        )

        # ========== 임베딩 필요 여부 플래그 ==========
        needs_embedding = total_changes > 0
        state["needs_embedding"] = needs_embedding
        logger.info(f"📦 임베딩 필요: {needs_embedding}")

        return state

    def _extract_reference_blocks(
        self, regul_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """regul_data에서 reference_blocks 추출 (Vision Pipeline 구조 대응)."""
        ref_blocks = []
        # Vision Pipeline 출력 구조
        vision_pages = regul_data.get("vision_extraction_result", [])

        doc_id = regul_data.get("regulation_id") or regul_data.get(
            "regulation", {}
        ).get("regulation_id")

        for page in vision_pages:
            structure = page.get("structure", {})
            page_num = page.get("page_num", 0)
            markdown_content = structure.get("markdown_content", "")
            reference_blocks = structure.get("reference_blocks", [])

            # reference_blocks가 있으면 사용
            if reference_blocks:
                lines = markdown_content.splitlines()
                for ref in reference_blocks:
                    start = max(0, ref.get("start_line", 0))
                    end = ref.get("end_line", len(lines))
                    if end <= start:
                        end = min(len(lines), start + 20)
                    snippet = "\n".join(lines[start:end]) if lines else markdown_content

                    kw = ref.get("keywords") or self._extract_keywords(snippet)

                    ref_blocks.append(
                        {
                            "section_ref": ref.get("section_ref", ""),
                            "text": snippet,
                            "keywords": kw,
                            "page_num": page_num,
                            "start_line": ref.get("start_line", 0),
                            "end_line": ref.get("end_line", 0),
                            "hierarchy": [],  # 계층 정보 (필요시 추가)
                            "doc_id": doc_id,
                            "meta_doc_id": doc_id,
                        }
                    )
            else:
                # reference_blocks가 없으면 페이지 전체를 하나의 블록으로
                ref_blocks.append(
                    {
                        "section_ref": f"Page {page_num}",
                        "text": markdown_content[:500],  # 처음 500자
                        "keywords": self._extract_keywords(markdown_content),
                        "page_num": page_num,
                        "start_line": 0,
                        "end_line": len(markdown_content.splitlines()),
                        "hierarchy": [],
                        "doc_id": doc_id,
                        "meta_doc_id": doc_id,
                    }
                )

        return ref_blocks

    def _extract_keywords(self, text: str, max_keywords: int = 5) -> List[str]:
        """텍스트에서 키워드 추출 (간단한 토큰 기반)."""
        import re

        if not text:
            return []

        # 숫자 포함 단어 우선 (예: 20mg, § 1141.1)
        numeric_words = re.findall(r"\b\w*\d+\w*\b", text)

        # 대문자 시작 단어 (고유명사)
        capitalized = re.findall(r"\b[A-Z][a-z]+\b", text)

        # 결합 및 중복 제거
        keywords = list(dict.fromkeys(numeric_words[:3] + capitalized[:3]))

        return keywords[:max_keywords]

    async def _find_legacy_regulation_db(
        self, regul_data: Dict[str, Any], db_session, exclude_regulation_id: int = None
    ) -> Optional[int]:
        """DB에서 Legacy 규제 검색 (강화된 검색 로직 + Citation Code 정규화)."""
        if not regul_data:
            logger.warning("regul_data가 None입니다")
            return None

        # vision_extraction_result에서 메타데이터 추출
        vision_pages = regul_data.get("vision_extraction_result", [])
        if not vision_pages:
            logger.warning("vision_extraction_result가 비어있습니다")
            return None

        first_page = vision_pages[0]
        metadata = first_page.get("structure", {}).get("metadata", {})

        title = metadata.get("title", "")
        country = metadata.get("jurisdiction_code", "")
        citation_code = metadata.get("citation_code", "")
        version = metadata.get("version", "")
        effective_date = metadata.get("effective_date", "")

        # Citation Code 정규화 (하이픈 제거, 대문자 변환)
        def normalize_citation(code: str) -> str:
            if not code:
                return ""
            return code.upper().replace("-", "").replace(" ", "")

        normalized_citation = normalize_citation(citation_code)

        logger.info(f"DB Legacy 검색: title={title}, country={country}")
        # noisy print 제거, logger로만 기록

        try:
            from app.core.repositories.regulation_repository import RegulationRepository

            repo = RegulationRepository()

            # 1순위: citation_code + country (정규화된 코드로 검색)
            if normalized_citation and country:
                # 원본 citation_code로 검색
                regulation = await repo.find_by_citation_and_country(
                    db_session, citation_code, country, exclude_regulation_id
                )
                if regulation:
                    logger.info(
                        f"DB Legacy 발견 (citation 원본): regulation_id={regulation.regulation_id}"
                    )
                    return regulation.regulation_id

                # 정규화된 citation_code로 재검색 (fallback)
                regulation = await repo.find_by_citation_normalized(
                    db_session, normalized_citation, country, exclude_regulation_id
                )
                if regulation:
                    logger.info(
                        f"DB Legacy 발견 (citation 정규화): regulation_id={regulation.regulation_id}"
                    )
                    return regulation.regulation_id

            # 2순위: title + country + version
            if title and country and version:
                regulation = await repo.find_by_title_country_version(
                    db_session, title, country, version, exclude_regulation_id
                )
                if regulation:
                    logger.info(
                        f"DB Legacy 발견 (title+version): regulation_id={regulation.regulation_id}"
                    )
                    return regulation.regulation_id

            # 3순위: title + country (기존 로직)
            if title and country:
                regulation = await repo.find_by_title_and_country(
                    db_session, title, country, exclude_regulation_id
                )
                if regulation:
                    logger.info(
                        f"DB Legacy 발견 (title): regulation_id={regulation.regulation_id}"
                    )
                    return regulation.regulation_id
            regulation = await repo.find_by_title_and_country(
                db_session, title, country, exclude_regulation_id
            )

            if regulation:
                logger.info(f"DB Legacy 발견: regulation_id={regulation.regulation_id}")
                return regulation.regulation_id

            logger.info("DB Legacy 미발견")
            return None

        except Exception as e:
            logger.error(f"DB Legacy 검색 실패: {e}")
            return None

    def _normalize_section_ref(self, section_ref: str) -> str:
        """조항 번호 정규화 (§1160.5, 1160.5, § 1160.5 → 1160.5)."""
        import re

        normalized = re.sub(r"[§\s]", "", section_ref)
        match = re.search(r"(\d+\.\d+)", normalized)
        return match.group(1) if match else normalized

    async def _match_reference_blocks(
        self, new_blocks: List[Dict[str, Any]], legacy_blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Strict Section Matching: 조항 번호 기반 정확한 1:1 매칭 (중복 제거).
        """
        logger.info("🔍 Strict Section Matching 시작 (중복 제거)")

        # 중복 제거: 같은 section_ref는 처음 하나만 사용
        def deduplicate_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            seen_sections = set()
            unique_blocks = []
            for block in blocks:
                section = self._normalize_section_ref(block.get("section_ref", ""))
                if section and section not in seen_sections:
                    seen_sections.add(section)
                    unique_blocks.append(block)
            return unique_blocks

        new_blocks_unique = deduplicate_blocks(new_blocks)
        legacy_blocks_unique = deduplicate_blocks(legacy_blocks)

        logger.info(
            f"🧹 중복 제거: New {len(new_blocks)} → {len(new_blocks_unique)}, "
            f"Legacy {len(legacy_blocks)} → {len(legacy_blocks_unique)}"
        )

        matched_pairs = []
        matched_legacy_sections = set()

        # 정규화된 조항 번호 기반 1:1 매칭
        for new_block in new_blocks_unique:
            new_section = new_block.get("section_ref", "")
            new_normalized = self._normalize_section_ref(new_section)

            if not new_normalized:
                continue

            for legacy_block in legacy_blocks_unique:
                legacy_section = legacy_block.get("section_ref", "")
                legacy_normalized = self._normalize_section_ref(legacy_section)

                if legacy_normalized in matched_legacy_sections:
                    continue

                if new_normalized == legacy_normalized:
                    matched_pairs.append(
                        {
                            "new_block": new_block,
                            "legacy_block": legacy_block,
                            "match_confidence": 1.0,
                            "match_reason": f"Exact section: {new_normalized}",
                        }
                    )
                    matched_legacy_sections.add(legacy_normalized)
                    logger.debug(f"✅ Matched: {new_section} ↔ {legacy_section}")
                    break

        # 매칭 실패한 섹션 로그
        unmatched_new = [
            b.get("section_ref")
            for b in new_blocks_unique
            if not any(p["new_block"] == b for p in matched_pairs)
        ]
        if unmatched_new:
            logger.warning(f"⚠️ 매칭 실패한 신규 섹션: {unmatched_new[:5]}...")

        logger.info(
            f"✅ 매칭 완료: {len(matched_pairs)}개 쌍 "
            f"(Exact: {sum(1 for p in matched_pairs if p['match_confidence'] == 1.0)})"
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
        new_doc_id = new_block.get("doc_id")
        legacy_doc_id = legacy_block.get("doc_id")

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

            # GPT-5 nano는 temperature 파라미터 미지원
            call_params = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": CHANGE_DETECTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            }

            # gpt-5-nano가 아닌 경우에만 temperature 추가
            if "gpt-5-nano" not in self.model_name.lower():
                call_params["temperature"] = 0.1

            response = await self.llm.chat.completions.create(**call_params)

            result = json.loads(response.choices[0].message.content)
            result["section_ref"] = section_ref
            result["new_ref_id"] = new_ref_id
            result["legacy_ref_id"] = legacy_ref_id
            result["doc_id"] = new_doc_id
            result["meta_doc_id"] = new_doc_id
            result.setdefault("new_snippet", new_text[:1000])
            result.setdefault("legacy_snippet", legacy_text[:1000])

            # 키워드/필드 보강 (검색/매핑 힌트용)
            kw: Set[str] = set(result.get("keywords") or [])
            kw |= set(self._extract_keywords(new_text, max_keywords=5))
            kw |= set(self._extract_keywords(legacy_text, max_keywords=5))
            for num_change in result.get("numerical_changes", []) or []:
                field = num_change.get("field")
                if field:
                    kw.add(str(field))
            if kw:
                result["keywords"] = list(kw)

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

    async def _analyze_new_regulation(
        self, regul_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """신규 규제 분석 (Legacy 없을 때 LLM으로 핵심 요구사항 추출)."""
        vision_pages = regul_data.get("vision_extraction_result", [])
        if not vision_pages:
            return {
                "regulation_summary": "",
                "key_requirements": [],
                "affected_areas": [],
            }

        # 전체 텍스트 추출 (최대 5000자)
        full_text = ""
        for page in vision_pages[:10]:  # 최대 10페이지
            markdown = page.get("structure", {}).get("markdown_content", "")
            full_text += markdown + "\n\n"

        full_text = full_text[:5000]

        user_prompt = f"""**Regulation Text:**
{full_text}
"""

        try:
            # GPT-5 nano는 temperature 파라미터 미지원
            call_params = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": NEW_REGULATION_ANALYSIS_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
            }

            # gpt-5-nano가 아닌 경우에만 temperature 추가
            if "gpt-5-nano" not in self.model_name.lower():
                call_params["temperature"] = 0.1

            response = await self.llm.chat.completions.create(**call_params)

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            logger.error(f"신규 규제 분석 실패: {e}")
            return {
                "regulation_summary": "",
                "key_requirements": [],
                "affected_areas": [],
            }


# ==================== 노드 함수 ====================
_default_node: Optional[ChangeDetectionNode] = None


async def change_detection_node(
    state: AppState, config: Dict[str, Any] = None
) -> AppState:
    """LangGraph 노드 엔트리포인트 (내부에서 짧은 세션 생성)."""
    global _default_node
    if _default_node is None:
        _default_node = ChangeDetectionNode()

    # 중복 실행 방지: 이미 결과가 있고 강제 재실행이 아닌 경우 skip
    if (
        state.get("change_detection_ran_inline")
        or state.get("change_detection_results")
    ) and not state.get("force_rerun_change_detection"):
        logger.info("change_detection 이미 실행됨. 재실행 건너뜀.")
        return state

    return await _default_node.run(state, db_session=None)


__all__ = ["ChangeDetectionNode", "change_detection_node", "ConfidenceScorer"]
