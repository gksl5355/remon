# app/ai_pipeline/nodes/change_detection.py
"""
module: change_detection.py
description: 규제 변경 감지 노드 (Reference ID 기반, 전처리 후 임베딩 전)
author: AI Agent
created: 2025-01-18
updated: 2025-01-22 (프롬프트 분리)
dependencies:
    - openai
    - app.vectorstore.vector_client
    - app.ai_pipeline.state
    - app.ai_pipeline.prompts.change_detection_prompt
"""

import json
import logging
from typing import Dict, Any, List, Optional, Literal, Set
from datetime import datetime
from openai import AsyncOpenAI
from sqlalchemy import text

from app.ai_pipeline.state import AppState
from app.vectorstore.vector_client import VectorClient
from app.ai_pipeline.prompts.change_detection_prompt import (
    CHANGE_DETECTION_SYSTEM_PROMPT,
    SECTION_MATCHING_PROMPT,
    NEW_REGULATION_ANALYSIS_PROMPT
)

logger = logging.getLogger(__name__)


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

    def _build_keynote_data(
        self,
        detection_results: List[Dict[str, Any]],
        change_summary: Dict[str, Any],
        regulation_meta: Dict[str, Any],
        legacy_regulation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Change Detection 결과를 Keynote JSON으로 변환"""
        from datetime import datetime

        return {
            "regulation_id": regulation_meta.get("regulation_id"),
            "country": regulation_meta.get("country"),
            "citation_code": regulation_meta.get("citation_code"),
            "title": regulation_meta.get("title"),
            "effective_date": regulation_meta.get("effective_date"),
            "analysis_date": datetime.utcnow().isoformat() + "Z",
            "change_summary": {
                "total_sections_analyzed": change_summary.get(
                    "total_reference_blocks", 0
                ),
                "total_changes_detected": change_summary.get("total_changes", 0),
                "high_confidence_changes": change_summary.get(
                    "high_confidence_changes", 0
                ),
            },
            "section_changes": [
                {
                    "section_ref": r.get("section_ref"),
                    "change_detected": r.get("change_detected"),
                    "confidence_level": r.get("confidence_level"),
                    "confidence_score": r.get("confidence_score"),
                    "change_type": r.get("change_type"),
                    "comparison": {
                        "legacy_snippet": r.get("legacy_snippet", "")[:200],
                        "new_snippet": r.get("new_snippet", "")[:200],
                    },
                    "reasoning": r.get("reasoning", {}),
                    "numerical_changes": r.get("numerical_changes", []),
                    "keywords": r.get("keywords", []),
                }
                for r in detection_results
                if r.get("change_detected")
            ],
            "legacy_regulation": (
                {"regulation_id": legacy_regulation_id}
                if legacy_regulation_id
                else None
            ),
        }

    async def run(self, state: AppState, db_session=None) -> AppState:
        """변경 감지 노드 실행 (짧은 DB 세션 사용)."""
        logger.info("=== Change Detection Node 시작 (Reference ID 기반) ===")
        # 신규 규제 데이터 가져오기 (preprocess_results 우선)
        pre_results = state.get("preprocess_results") or []
        if not pre_results:
            logger.info("preprocess_results 없음, 변경 감지 스킵")
            state["change_detection_results"] = []
            state["change_summary"] = {
                "status": "skipped",
                "reason": "no_preprocess_results",
            }
            # 실행 상태 마킹
            self._mark_execution_state(state)
            return state

        new_regul_data = pre_results[0]
        if new_regul_data.get("status") != "success":
            logger.error("❌ 전처리 실패, 변경 감지 스킵")
            state["change_detection_results"] = []
            state["change_summary"] = {"status": "error", "reason": "preprocess_failed"}
            return state

        new_regulation_id = new_regul_data.get("regulation_id", "NEW")
        legacy_regul_data = None
        legacy_regulation_id = None  # 초기화

        # citation_code 기반으로 Legacy 검색 (새 DB 세션 생성)
        if not legacy_regul_data:
            from app.core.repositories.regulation_repository import RegulationRepository
            from app.core.database import AsyncSessionLocal

            repo = RegulationRepository()
            # 새 세션 생성 (이전 세션 연결 끊김 방지)
            async with AsyncSessionLocal() as session:
                if not new_regul_data:
                    if not new_regulation_id:
                        logger.error("new_regulation_id 없음")
                        state["change_detection_results"] = []
                        state["change_summary"] = {
                            "status": "error",
                            "reason": "no_new_regulation_id",
                        }
                        self._mark_execution_state(state)
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
                        self._mark_execution_state(state)
                        return state

                if not legacy_regul_data:
                    # citation_code 기반으로 Legacy 검색 (regulation_id 무시)
                    logger.info(f"🔍 new_regul_data 확인: {bool(new_regul_data)}")
                    if new_regul_data:
                        logger.info(
                            f"   new_regul_data keys: {list(new_regul_data.keys())}"
                        )

                    vision_pages = (
                        new_regul_data.get("vision_extraction_result", [])
                        if new_regul_data
                        else []
                    )
                    logger.info(f"   vision_pages 개수: {len(vision_pages)}")

                    if vision_pages:
                        structure = vision_pages[0].get("structure", {})
                        new_metadata = structure.get("metadata") or {}
                        new_citation = new_metadata.get("citation_code")
                        new_country = new_metadata.get("jurisdiction_code")

                        if new_citation and new_country:
                            logger.info(
                                f"🔍 citation_code로 Legacy 검색: {new_citation} ({new_country})"
                            )

                            # citation_code + country로 Legacy 직접 조회 (월-일 기준)
                            try:
                                result = await session.execute(
                                    text(
                                        """
                                        SELECT regul_data FROM regulations
                                        WHERE citation_code = :citation
                                        AND country_code = :country
                                        AND TO_CHAR(created_at, 'MMDD') < TO_CHAR(CURRENT_TIMESTAMP, 'MMDD')
                                        ORDER BY created_at DESC LIMIT 1
                                    """
                                    ),
                                    {"citation": new_citation, "country": new_country},
                                )
                                row = result.fetchone()
                                if row:
                                    legacy_regul_data = row[0]
                                    logger.info(
                                        f"✅ Legacy 발견 (월-일 기준): citation={new_citation}"
                                    )
                            except Exception as db_err:
                                logger.error(f"❌ DB 쿼리 실패 (연결 끊김): {db_err}")
                                logger.info("⚠️ Legacy 검색 실패 - 신규 규제로 처리")

                    if not legacy_regul_data:
                        logger.warning("⚠️ Legacy 검색 실패 - 신규 규제로 처리")
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

                        # 🆕 신규 규제 Keynote 데이터 생성
                        keynote_data = {
                            "regulation_id": new_regulation_id,
                            "country": new_country,
                            "citation_code": new_citation,
                            "title": new_metadata.get("title", "Unknown Regulation"),
                            "effective_date": new_metadata.get("effective_date"),
                            "analysis_date": datetime.utcnow().isoformat() + "Z",
                            "change_summary": {
                                "total_sections_analyzed": 0,
                                "total_changes_detected": 0,
                                "high_confidence_changes": 0,
                            },
                            "section_changes": [],  # 신규 규제는 변경 사항 없음
                            "new_regulation_analysis": analysis_hints,  # 신규 분석 결과 추가
                            "legacy_regulation": None,
                        }
                        state["change_keynote_data"] = keynote_data
                        logger.info("📝 신규 규제 Keynote 데이터 생성 완료")
                        logger.info(f"   - regulation_id: {new_regulation_id}")
                        logger.info(f"   - country: {new_country}")
                        logger.info(f"   - citation_code: {new_citation}")
                        logger.info(f"   - key_requirements: {len(analysis_hints.get('key_requirements', []))}개")
                        
                        state["change_detection_results"] = []
                        state["change_summary"] = {
                            "status": "new_regulation",
                            "total_changes": 0,
                        }
                        state["needs_embedding"] = True
                        self._mark_execution_state(state)
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

        # ========== 최종 검증: legacy_regul_data 확인 ==========
        if not legacy_regul_data:
            logger.error("❌ legacy_regul_data가 None입니다")
            logger.error(
                "💡 해결: python scripts/run_full_pipeline.py --mode legacy 실행 필요"
            )
            state["change_detection_results"] = []
            state["change_summary"] = {
                "status": "error",
                "reason": "legacy_data_is_none",
                "message": "Legacy 규제를 먼저 DB에 저장하세요 (--mode legacy)",
            }
            return state

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

        # ========== Keynote 데이터 생성 ==========
        regulation_meta = state.get("regulation", {})
        keynote_data = self._build_keynote_data(
            detection_results=detection_results,
            change_summary=state["change_summary"],
            regulation_meta=regulation_meta,
            legacy_regulation_id=legacy_regulation_id,
        )
        state["change_keynote_data"] = keynote_data
        logger.info("📝 Change Keynote 데이터 생성 완료")
        logger.info(f"   - 데이터 크기: {len(str(keynote_data))} bytes")
        logger.info(f"   - section_changes: {len(keynote_data.get('section_changes', []))}개")
        logger.info(f"   - regulation_id: {keynote_data.get('regulation_id')}")

        # ========== 임베딩 필요 여부 플래그 ==========
        needs_embedding = total_changes > 0
        state["needs_embedding"] = needs_embedding
        logger.info(f"📦 임베딩 필요: {needs_embedding}")

        # 실행 상태 마킹 (정상 완료)
        self._mark_execution_state(state)
        
        # ✅ 최종 확인: state에 change_keynote_data가 제대로 저장되었는지 확인
        if "change_keynote_data" not in state:
            logger.error("❌ change_keynote_data가 state에 저장되지 않았습니다!")
        else:
            logger.info(f"✅ state['change_keynote_data'] 확인 완료: {len(str(state['change_keynote_data']))} bytes")
        
        return state

    def _extract_reference_blocks(
        self, regul_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Reference Block 추출 (메타데이터 기반)."""
        ref_blocks = []
        vision_pages = regul_data.get("vision_extraction_result", [])
        doc_id = regul_data.get("regulation_id") or regul_data.get("regulation", {}).get("regulation_id")

        for page in vision_pages:
            structure = page.get("structure", {})
            page_num = page.get("page_num", 0)
            markdown_content = structure.get("markdown_content", "")
            reference_blocks_meta = structure.get("reference_blocks", [])

            if reference_blocks_meta:
                lines = markdown_content.splitlines()
                for ref in reference_blocks_meta:
                    start = max(0, ref.get("start_line", 0))
                    end = ref.get("end_line", len(lines))
                    if end <= start:
                        end = min(len(lines), start + 20)
                    snippet = "\n".join(lines[start:end]) if lines else markdown_content
                    ref_blocks.append({
                        "section_ref": ref.get("section_ref", ""),
                        "text": snippet,
                        "keywords": ref.get("keywords") or self._extract_keywords(snippet),
                        "page_num": page_num,
                        "doc_id": doc_id,
                        "meta_doc_id": doc_id,
                    })
            else:
                ref_blocks.append({
                    "section_ref": f"Page {page_num}",
                    "text": markdown_content[:500],
                    "keywords": self._extract_keywords(markdown_content),
                    "page_num": page_num,
                    "doc_id": doc_id,
                    "meta_doc_id": doc_id,
                })

        logger.info(f"Reference Blocks 추출: {len(ref_blocks)}개")
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
        """DB에서 Legacy 규제 검색 (강화된 검색 로직 + Citation Code 정규화 + 같은 날짜 필터링)."""
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

            # 같은 날짜 필터링을 위한 신규 규제 created_at 조회
            exclude_date = None
            if exclude_regulation_id:
                result = await db_session.execute(
                    text(
                        "SELECT DATE(created_at) FROM regulations WHERE regulation_id = :rid"
                    ),
                    {"rid": exclude_regulation_id},
                )
                row = result.fetchone()
                if row:
                    exclude_date = row[0]

            # 1순위: citation_code + country (정규화된 코드로 검색)
            if normalized_citation and country:
                # 원본 citation_code로 검색 (같은 날짜 제외)
                if exclude_date:
                    result = await db_session.execute(
                        text(
                            """
                            SELECT regulation_id FROM regulations
                            WHERE citation_code = :citation
                            AND country_code = :country
                            AND DATE(created_at) < :exclude_date
                            AND (:exclude_id IS NULL OR regulation_id != :exclude_id)
                            ORDER BY created_at DESC LIMIT 1
                        """
                        ),
                        {
                            "citation": citation_code,
                            "country": country,
                            "exclude_date": exclude_date,
                            "exclude_id": exclude_regulation_id,
                        },
                    )
                    row = result.fetchone()
                    regulation = await repo.get(db_session, row[0]) if row else None
                else:
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
        Strict Section Matching: 조항 번호 기반 정확한 1:1 매칭 (텍스트 병합).
        """
        logger.info("🔍 Strict Section Matching 시작 (텍스트 병합)")

        # 중복 제거 + 텍스트 병합: 같은 section_ref의 모든 텍스트를 병합
        def deduplicate_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            section_map = {}  # {section_ref: merged_block}

            for block in blocks:
                section = self._normalize_section_ref(block.get("section_ref", ""))
                if not section:
                    continue

                if section not in section_map:
                    # 첫 발견: 초기화
                    section_map[section] = block.copy()
                    section_map[section]["end_page"] = block.get("page_num")
                    section_map[section]["page_range"] = [block.get("page_num")]
                else:
                    # 재발견: 텍스트 병합
                    existing_text = section_map[section].get("text", "")
                    new_text = block.get("text", "")
                    section_map[section]["text"] = existing_text + "\n\n" + new_text
                    section_map[section]["end_page"] = block.get("page_num")
                    section_map[section]["page_range"].append(block.get("page_num"))

            return list(section_map.values())

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

            # GPT-5: Chat Completions API (SDK 버전 호환성)
            response = await self.llm.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": CHANGE_DETECTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
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

    def _mark_execution_state(self, state: AppState) -> None:
        """실행 상태 마킹 (중복 실행 방지)."""
        state["change_detection_ran_inline"] = True
    
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
            # GPT-5: Chat Completions API (SDK 버전 호환성)
            response = await self.llm.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": NEW_REGULATION_ANALYSIS_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
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
