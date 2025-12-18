# app/ai_pipeline/nodes/change_detection.py
"""
module: change_detection.py
description: 규제 변경 감지 노드 (Reference ID 기반, 전처리 후 임베딩 전)
author: AI Agent
created: 2025-01-18
updated: 2025-01-23 (HITL 기능 추가 - refined_change_detection_prompt 지원)
dependencies:
    - openai
    - app.vectorstore.vector_client
    - app.ai_pipeline.state
    - app.ai_pipeline.prompts.change_detection_prompt
    - app.core.repositories.regulation_keynote_repository
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
    NEW_REGULATION_ANALYSIS_PROMPT,
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
        if confidence >= 0.8:  # 완화: 0.9 → 0.8
            return "HIGH"
        elif confidence >= 0.5:  # 완화: 0.7 → 0.5
            return "MEDIUM"
        elif confidence >= 0.4:  # 완화: 0.5 → 0.4
            return "LOW"
        else:
            return "UNCERTAIN"


##sa-mj 통합 (160 - 236)
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
                        "legacy_snippet": r.get("legacy_snippet", ""),
                        "new_snippet": r.get("new_snippet", ""),
                    },
                    "reasoning": r.get("reasoning", {}),
                    "numerical_changes": r.get("numerical_changes", []),
                    "keywords": r.get("keywords", []),
                    "new_ref_id": r.get("new_ref_id"),
                    "legacy_ref_id": r.get("legacy_ref_id"),
                }
                for r in detection_results
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

                        if vision_pages:
                            new_metadata = (
                                vision_pages[0].get("structure", {}).get("metadata", {})
                            )
                            new_citation = new_metadata.get("citation_code")
                            new_country = new_metadata.get("jurisdiction_code")

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

                    # 여전히 legacy_regul_data 없으면 → 완전 신규 규제 처리
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
                        logger.info("📝 신규 규제 Keynote 데이터 생성 완료 (report 노드에서 저장 예정)")
                        logger.info(f"   - regulation_id: {new_regulation_id}")
                        logger.info(f"   - country: {new_country}")
                        logger.info(f"   - citation_code: {new_citation}")
                        logger.info(
                            f"   - key_requirements: {len(analysis_hints.get('key_requirements', []))}개"
                        )

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
                    pair, new_regulation_id, legacy_regulation_id, state
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

        # 중복 제거 (Section 기준)
        seen_sections = {}
        for result in detection_results:
            section = self._normalize_section_ref(result.get("section_ref", ""))
            if not section:
                continue
            
            # 같은 Section이 있으면 신뢰도 높은 것만 유지
            if section in seen_sections:
                existing = seen_sections[section]
                if result.get("confidence_score", 0) > existing.get("confidence_score", 0):
                    seen_sections[section] = result
            else:
                seen_sections[section] = result
        
        detection_results = list(seen_sections.values())
        logger.info(f"🔄 중복 제거 후: {len(detection_results)}개 유니크 섹션")
        
        # 신뢰도 조정 및 필터링
        filtered_results = []
        for result in detection_results:
            result["confidence_score"] = self.confidence_scorer.adjust_confidence(result)
            result["confidence_level"] = self.confidence_scorer.get_confidence_level(
                result["confidence_score"]
            )
            
            # LOW/UNCERTAIN 필터링 (완화된 조건)
            if result.get("change_detected"):
                if result["confidence_score"] >= 0.5:  # 완화: 0.65 → 0.5
                    filtered_results.append(result)
                else:
                    logger.debug(f"⚠️ 낮은 신뢰도로 제외: {result.get('section_ref')} ({result['confidence_score']:.2f})")
            else:
                # 변경 없음도 완화
                if result["confidence_score"] >= 0.55:  # 완화: 0.7 → 0.55
                    filtered_results.append(result)
        
        # 필터링 전 전체 결과 백업 (Keynote 저장용)
        all_detection_results = detection_results.copy()
        
        detection_results = filtered_results
        logger.info(f"✅ 신뢰도 필터링 후: {len(detection_results)}개")
        
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
            detection_results=all_detection_results,
            change_summary=state["change_summary"],
            regulation_meta=regulation_meta,
            legacy_regulation_id=legacy_regulation_id,
        )
        state["change_keynote_data"] = keynote_data
        logger.info("📝 Change Keynote 데이터 생성 완료 (report 노드에서 저장 예정)")
        logger.info(f"   - 데이터 크기: {len(str(keynote_data))} bytes")
        logger.info(
            f"   - section_changes: {len(keynote_data.get('section_changes', []))}개"
        )
        logger.info(f"   - regulation_id: {keynote_data.get('regulation_id')}")

        # ========== 중간 결과물 저장 (HITL용) ==========
        from app.core.repositories.intermediate_output_repository import IntermediateOutputRepository
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            intermediate_repo = IntermediateOutputRepository()
            
            # 🆕 중간 결과물 저장 (HITL용)
            try:
                intermediate_data = {
                    "change_detection_results": detection_results,
                    "change_summary": state["change_summary"],
                    "change_detection_index": change_index,
                    "regulation_analysis_hints": state.get("regulation_analysis_hints", {})
                }
                await intermediate_repo.save_intermediate(
                    session,
                    regulation_id=new_regulation_id,
                    node_name="change_detection",
                    data=intermediate_data
                )
                await session.commit()
                logger.info(f"✅ 변경 감지 중간 결과물 저장 완료: regulation_id={new_regulation_id}")
            except Exception as db_err:
                await session.rollback()
                logger.error(f"❌ 중간 결과물 저장 실패: {db_err}")
                import traceback
                traceback.print_exc()

        # ========== 임베딩 필요 여부 플래그 ==========
        needs_embedding = total_changes > 0
        state["needs_embedding"] = needs_embedding
        logger.info(f"📦 임베딩 필요: {needs_embedding}")

        # 실행 상태 마킹 (정상 완료)
        self._mark_execution_state(state)

        return state

    def _extract_reference_blocks(
        self, regul_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Reference Block 추출 (메타데이터 기반)."""
        ref_blocks = []
        vision_pages = regul_data.get("vision_extraction_result", [])
        doc_id = regul_data.get("regulation_id") or regul_data.get(
            "regulation", {}
        ).get("regulation_id")

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
                    ref_blocks.append(
                        {
                            "section_ref": ref.get("section_ref", ""),
                            "text": snippet,
                            "keywords": ref.get("keywords")
                            or self._extract_keywords(snippet),
                            "page_num": page_num,
                            "doc_id": doc_id,
                            "meta_doc_id": doc_id,
                        }
                    )
            else:
                ref_blocks.append(
                    {
                        "section_ref": f"Page {page_num}",
                        "text": markdown_content[:500],
                        "keywords": self._extract_keywords(markdown_content),
                        "page_num": page_num,
                        "doc_id": doc_id,
                        "meta_doc_id": doc_id,
                    }
                )

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
        LLM 기반 능동적 매칭: 전체 컨텍스트를 LLM에 전달하여 의미적 매칭 수행.
        """
        logger.info("🤖 LLM 기반 능동적 매칭 시작")

        # 블록 요약 (LLM 입력 크기 최대화 - GPT-4o-mini 128K 토큰)
        def summarize_blocks(blocks: List[Dict[str, Any]], max_blocks: int = 100) -> List[Dict[str, Any]]:
            """블록 요약 (최대 100개, 각 2000자 - 미탐 방지)"""
            summarized = []
            for idx, block in enumerate(blocks[:max_blocks]):
                summarized.append({
                    "id": f"block_{idx}",
                    "section_ref": block.get("section_ref", f"Page {block.get('page_num')}"),
                    "text_preview": block.get("text", "")[:2000],  # 300 → 2000자
                    "keywords": block.get("keywords", [])[:10],  # 5 → 10개
                    "page_num": block.get("page_num")
                })
            return summarized

        new_summary = summarize_blocks(new_blocks)
        legacy_summary = summarize_blocks(legacy_blocks)

        # LLM 매칭 프롬프트
        prompt = f"""You are a regulatory document comparison expert.

**Task**: Match corresponding blocks between NEW and LEGACY regulations based on semantic similarity.

**NEW Regulation Blocks** ({len(new_summary)} blocks):
{json.dumps(new_summary, indent=2, ensure_ascii=False)}

**LEGACY Regulation Blocks** ({len(legacy_summary)} blocks):
{json.dumps(legacy_summary, indent=2, ensure_ascii=False)}

**Instructions**:
1. Match blocks that discuss the SAME regulatory topic (even if section numbers differ)
2. Consider: keywords, content similarity, regulatory intent
3. Return ONLY matched pairs (skip unmatched blocks)
4. Assign confidence: 1.0 (exact), 0.8 (high), 0.6 (medium), 0.4 (low)

**Output JSON** (array of matches):
[
  {{
    "new_block_id": "block_0",
    "legacy_block_id": "block_3",
    "confidence": 0.9,
    "reason": "Both discuss nicotine concentration limits"
  }}
]

**CRITICAL**: Return ONLY valid JSON array. If no matches, return [].
"""

        try:
            response = await self.llm.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a regulatory document matcher. Return JSON only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            
            # JSON 파싱 (배열 또는 객체 처리)
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and "matches" in parsed:
                    matches = parsed["matches"]
                elif isinstance(parsed, list):
                    matches = parsed
                else:
                    matches = []
            except json.JSONDecodeError:
                logger.error(f"LLM 매칭 JSON 파싱 실패: {content[:200]}")
                matches = []

            # 매칭 결과를 matched_pairs 형태로 변환
            matched_pairs = []
            for match in matches:
                new_id = match.get("new_block_id", "")
                legacy_id = match.get("legacy_block_id", "")
                
                try:
                    new_idx = int(new_id.split("_")[1])
                    legacy_idx = int(legacy_id.split("_")[1])
                    
                    if new_idx < len(new_blocks) and legacy_idx < len(legacy_blocks):
                        matched_pairs.append({
                            "new_block": new_blocks[new_idx],
                            "legacy_block": legacy_blocks[legacy_idx],
                            "match_confidence": match.get("confidence", 0.5),
                            "match_reason": match.get("reason", "LLM semantic match")
                        })
                except (IndexError, ValueError) as e:
                    logger.warning(f"매칭 인덱스 파싱 실패: {e}")
                    continue

            logger.info(f"✅ LLM 매칭 완료: {len(matched_pairs)}개 쌍")
            return matched_pairs

        except Exception as e:
            logger.error(f"❌ LLM 매칭 실패, Fallback 사용: {e}")
            return self._fallback_keyword_matching(new_blocks, legacy_blocks)

    def _fallback_keyword_matching(
        self, new_blocks: List[Dict[str, Any]], legacy_blocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """LLM 실패 시 키워드 기반 매칭."""
        logger.info("🔄 Fallback: 키워드 기반 매칭")
        matched_pairs = []
        matched_legacy = set()

        for new_block in new_blocks[:100]:  # 20 → 100
            new_kw = set(new_block.get("keywords", []))
            if not new_kw:
                continue

            best_match = None
            best_score = 0.0

            for idx, legacy_block in enumerate(legacy_blocks[:100]):  # 20 → 100
                if idx in matched_legacy:
                    continue

                legacy_kw = set(legacy_block.get("keywords", []))
                if not legacy_kw:
                    continue

                score = len(new_kw & legacy_kw) / len(new_kw | legacy_kw) if (new_kw | legacy_kw) else 0.0

                if score > best_score and score >= 0.3:
                    best_score = score
                    best_match = (idx, legacy_block)

            if best_match:
                matched_pairs.append({
                    "new_block": new_block,
                    "legacy_block": best_match[1],
                    "match_confidence": best_score,
                    "match_reason": f"Keyword fallback: {best_score:.2f}"
                })
                matched_legacy.add(best_match[0])

        logger.info(f"✅ Fallback 매칭: {len(matched_pairs)}개 쌍")
        return matched_pairs

    async def _detect_change_by_ref_id(
        self, pair: Dict[str, Any], new_regulation_id: str, legacy_regulation_id: str, state: Optional[AppState] = None
    ) -> Optional[Dict[str, Any]]:
        """CoT Step 2-4: Reference ID 기반 정밀 변경 감지 (Agentic + HITL)."""
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

        # 🆕 HITL: DB에서 기존 결과 로드 + 전문가 프롬프트 조합
        hitl_context = ""
        if state and state.get("refined_change_detection_prompt"):
            # DB에서 기존 변경 감지 결과 로드
            from app.core.repositories.intermediate_output_repository import IntermediateOutputRepository
            from app.core.database import AsyncSessionLocal
            
            regulation_id = state.get("regulation", {}).get("regulation_id")
            if regulation_id:
                try:
                    async with AsyncSessionLocal() as session:
                        intermediate_repo = IntermediateOutputRepository()
                        existing_data = await intermediate_repo.get_intermediate(
                            session, regulation_id, "change_detection"
                        )
                        
                        if existing_data and existing_data.get("change_detection_results"):
                            # 해당 섹션의 기존 결과 찾기
                            existing_results = existing_data["change_detection_results"]
                            section_result = next(
                                (r for r in existing_results if r.get("section_ref") == section_ref),
                                None
                            )
                            
                            if section_result:
                                hitl_context = f"""\n\n[EXISTING ANALYSIS - For Reference]
Previous Detection: {section_result.get('change_detected')}
Previous Confidence: {section_result.get('confidence_score')}
Previous Type: {section_result.get('change_type')}
Previous Reasoning: {section_result.get('reasoning', {})}

[EXPERT GUIDANCE]
{state['refined_change_detection_prompt']}

**CRITICAL**: Re-evaluate based on expert guidance above.
"""
                                logger.info(f"✅ HITL: Section {section_ref} - 기존 결과 + 전문가 프롬프트 적용")
                except Exception as e:
                    logger.warning(f"⚠️ HITL 컨텍스트 로드 실패: {e}")

        # LLM 호출 (ref_id 기반 정밀 비교 + HITL)
        try:
            prompt = f"""Perform PRECISE comparison using Reference IDs for context-aware analysis.

**Reference IDs:**
- Legacy: {legacy_ref_id}
- New: {new_ref_id}

**Legacy Regulation (Section {section_ref}):**
{legacy_text[:3000]}

**New Regulation (Section {section_ref}):**
{new_text[:3000]}{hitl_context}

**Task**: 
1. Use Reference IDs to understand document context and hierarchy
2. Detect ALL substantive changes (numerical, wording, scope)
3. Follow Chain of Thought (4 steps)
4. Apply Adversarial Validation
5. Extract numerical changes with full context

**CRITICAL**: Return valid JSON only. If unsure, set change_detected=false.
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

            # 유연한 JSON 파싱 (파싱 실패 시 fallback)
            content = response.choices[0].message.content
            try:
                result = json.loads(content)
            except json.JSONDecodeError as parse_err:
                logger.warning(
                    f"JSON 파싱 실패 (Section {section_ref}), fallback 사용: {parse_err}"
                )
                logger.debug(f"원본 응답: {content[:200]}...")
                result = {
                    "change_detected": False,
                    "confidence_score": 0.0,
                    "change_type": "parse_error",
                    "reasoning": {
                        "error": "LLM JSON 파싱 실패",
                        "raw_response": content[:500],
                    },
                    "numerical_changes": [],
                    "keywords": [],
                }
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
                "confidence_level": "UNCERTAIN",
                "change_type": "llm_error",
                "reasoning": {"error": str(e)},
                "numerical_changes": [],
                "keywords": [],
                "new_snippet": new_text[:500],
                "legacy_snippet": legacy_text[:500],
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
