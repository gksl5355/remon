"""
module: ai_service.py
description: AI 파이프라인 실행 및 State 복원 서비스
author: AI Agent
created: 2025-01-23
updated: 2025-01-23
dependencies:
    - app.ai_pipeline.graph
    - app.core.repositories.intermediate_output_repository
    - app.core.repositories.regulation_repository
"""

import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_pipeline.graph import build_graph
from app.ai_pipeline.state import AppState
from app.core.repositories.intermediate_output_repository import IntermediateOutputRepository
from app.core.repositories.regulation_repository import RegulationRepository

logger = logging.getLogger(__name__)


class AIService:
    """AI 파이프라인 실행 및 State 관리 서비스."""
    
    def __init__(self):
        self.intermediate_repo = IntermediateOutputRepository()
        self.regulation_repo = RegulationRepository()
    
    async def restore_state_from_db(
        self,
        db: AsyncSession,
        regulation_id: int
    ) -> AppState:
        """
        DB에서 중간 결과물을 로드하여 State 복원.
        
        Args:
            db: DB 세션
            regulation_id: 규제 ID
            
        Returns:
            AppState: 복원된 State
        """
        logger.info(f"State 복원 시작: regulation_id={regulation_id}")
        
        # 1. 중간 결과물 로드
        intermediate_data = await self.intermediate_repo.get_intermediate(
            db, regulation_id=regulation_id
        )
        
        if not intermediate_data:
            raise ValueError(f"regulation_id={regulation_id}의 중간 결과물이 없습니다.")
        
        # 2. 규제 메타데이터 로드
        regulation = await self.regulation_repo.get_regul_data(db, regulation_id)
        
        if not regulation:
            raise ValueError(f"regulation_id={regulation_id}의 규제 정보가 없습니다.")
        
        # 3. State 구성
        state = AppState(
            regulation={
                "regulation_id": regulation_id,
                "country": regulation.get("country"),
                "title": regulation.get("title"),
                "citation_code": regulation.get("citation_code"),
            },
            preprocess_results=[{
                "regulation_id": regulation_id,
                "status": "success",
                "vision_extraction_result": regulation.get("vision_extraction_result", [])
            }]
        )
        
        # 4. 중간 결과물 복원
        if "change_detection" in intermediate_data:
            cd_data = intermediate_data["change_detection"]
            state["change_detection_results"] = cd_data.get("change_detection_results", [])
            state["change_summary"] = cd_data.get("change_summary", {})
            state["change_detection_index"] = cd_data.get("change_detection_index", {})
            state["regulation_analysis_hints"] = cd_data.get("regulation_analysis_hints", {})
        
        if "map_products" in intermediate_data:
            mp_data = intermediate_data["map_products"]
            state["mapping"] = mp_data.get("mapping")
            state["product_info"] = mp_data.get("product_info")
        
        if "generate_strategy" in intermediate_data:
            gs_data = intermediate_data["generate_strategy"]
            state["strategies"] = gs_data.get("strategies", [])
        
        if "score_impact" in intermediate_data:
            si_data = intermediate_data["score_impact"]
            state["impact_scores"] = si_data.get("impact_scores", [])
        
        logger.info(f"✅ State 복원 완료: {len(intermediate_data)}개 노드")
        
        return state
    
    async def run_pipeline_with_hitl(
        self,
        db: AsyncSession,
        regulation_id: int,
        user_message: str,
        target_node: str
    ) -> Dict[str, Any]:
        """
        HITL 피드백을 반영하여 파이프라인 재실행.
        
        Args:
            db: DB 세션
            regulation_id: 규제 ID
            user_message: 사용자 피드백
            target_node: 재시작 노드
            
        Returns:
            Dict: 실행 결과 (report_id 포함)
        """
        logger.info(
            f"HITL 파이프라인 재실행: regulation_id={regulation_id}, "
            f"target_node={target_node}"
        )
        
        # 1. State 복원 (빠르게 완료)
        state = await self.restore_state_from_db(db, regulation_id)
        
        # 2. HITL 피드백 주입
        state["external_hitl_feedback"] = user_message
        state["hitl_target_node"] = target_node
        
        # ✅ DB 세션 조기 종료 (타임아웃 방지)
        await db.commit()
        await db.close()
        
        # 3. Graph 재실행 (target_node부터) - 독립 세션 사용
        graph = build_graph(start_node=target_node)
        result = await graph.ainvoke(state)
        
        # 4. 결과 추출
        report = result.get("report", {})
        report_id = report.get("report_id")
        
        logger.info(
            f"✅ HITL 파이프라인 완료: report_id={report_id}, "
            f"restarted_from={target_node}"
        )
        
        return {
            "status": "completed",
            "report_id": report_id,
            "restarted_from": target_node,
            "regulation_id": regulation_id
        }
    
    async def run_multi_file_pipeline(
        self,
        pdf_paths: List[str],
        product_info: Optional[Dict[str, Any]] = None,
        vision_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        복수 파일을 각각 독립적인 파이프라인으로 처리 (순차 실행, HITL 제외).
        
        Args:
            pdf_paths: PDF 파일 경로 리스트
            product_info: 제품 정보 (선택)
            vision_config: Vision Pipeline 설정 (선택)
            
        Returns:
            Dict: {
                "total": 전체 파일 수,
                "succeeded": 성공 수,
                "failed": 실패 수,
                "reports": [보고서 리스트]
            }
        """
        if not pdf_paths:
            return {"total": 0, "succeeded": 0, "failed": 0, "reports": []}
        
        logger.info(f"다중 파일 파이프라인 시작: {len(pdf_paths)}개 파일")
        
        reports = []
        succeeded = 0
        failed = 0
        
        for i, pdf_path in enumerate(pdf_paths, 1):
            try:
                logger.info(f"[{i}/{len(pdf_paths)}] 파일 처리: {pdf_path}")
                
                state = AppState(
                    preprocess_request={
                        "pdf_paths": [pdf_path],
                        "product_info": product_info,
                        "use_vision_pipeline": True,
                        "vision_config": vision_config,
                        "enable_change_detection": True
                    }
                )
                
                graph = build_graph()
                result = await graph.ainvoke(state)
                
                report = result.get("report", {})
                if report and report.get("report_id"):
                    succeeded += 1
                    reports.append(report)
                    logger.info(f"✅ [{i}/{len(pdf_paths)}] 완료: report_id={report.get('report_id')}")
                else:
                    failed += 1
                    reports.append({"status": "failed", "pdf_path": pdf_path})
                    
            except Exception as e:
                failed += 1
                reports.append({"status": "error", "pdf_path": pdf_path, "error": str(e)})
                logger.error(f"❌ [{i}/{len(pdf_paths)}] 실패: {e}", exc_info=True)
        
        logger.info(f"✅ 다중 파일 완료: {succeeded}/{len(pdf_paths)} 성공")
        
        return {
            "total": len(pdf_paths),
            "succeeded": succeeded,
            "failed": failed,
            "reports": reports
        }
