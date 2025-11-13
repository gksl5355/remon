"""LangGraph node: compose_report"""

"""
요약 리포트 생성 노드
규제 변경 내용 + 영향평가 → 통합 요약 리포트 생성

Author: 남지수 (BE2 - Database Engineer)
"""

from typing import Dict, Any, Optional
import logging
from datetime import datetime

from app.ai_pipeline.state import AppState
from app.ai_pipeline.chains.report_chain import ReportGeneratorChain


# 로깅 설정
logger = logging.getLogger(__name__)


async def report_node(state: AppState) -> Dict[str, Any]:
    """
    규제 변경 내용과 영향평가를 기반으로 요약 리포트 생성
    
    입력 (State):
        - regulation_text: 규제 원문 또는 normalized_text
        - impact_scores: 제품별 영향도 점수 딕셔너리
        - metadata: 국가, 시행일 등 메타데이터
    
    출력 (State 업데이트):
        - report_summary: 생성된 요약 리포트 텍스트
        - report_data: 리포트 메타데이터
        - error_log: 에러 발생 시 로그 추가
    
    Returns:
        Dict[str, Any]: State 업데이트용 딕셔너리
    """
    
    logger.info("=== 요약 리포트 생성 노드 시작 ===")
    
    # ==========================================
    # 1️⃣ 입력 데이터 추출 및 검증
    # ==========================================
    try:
        regulation_text = _extract_regulation_text(state)
        impact_scores = _extract_impact_scores(state)
        metadata = state.metadata or {}
        
        # 데이터 유효성 검증
        validation_result = _validate_inputs(
            regulation_text, 
            impact_scores, 
            state.error_log or []
        )
        
        if not validation_result["is_valid"]:
            logger.warning(f"입력 데이터 검증 실패: {validation_result['errors']}")
            return {
                "report_summary": None,
                "error_log": validation_result["errors"]
            }
        
        logger.info(f"입력 데이터 검증 완료 - 규제 텍스트 길이: {len(regulation_text)}, "
                   f"영향 제품 수: {len(impact_scores)}")
        
    except Exception as e:
        logger.error(f"입력 데이터 추출 중 오류: {str(e)}")
        return {
            "report_summary": None,
            "error_log": (state.error_log or []) + [f"데이터 추출 실패: {str(e)}"]
        }
    
    # ==========================================
    # 2️⃣ 리포트 생성 방식 결정
    # ==========================================
    use_llm = metadata.get("use_llm", True)  # 기본값: LLM 사용
    
    try:
        if use_llm:
            # LLM 기반 리포트 생성
            report_summary = await _generate_llm_report(
                regulation_text=regulation_text,
                impact_scores=impact_scores,
                metadata=metadata
            )
            generation_method = "LLM"
        else:
            # Template 기반 리포트 생성 (빠른 처리용)
            report_summary = _generate_template_report(
                regulation_text=regulation_text,
                impact_scores=impact_scores,
                metadata=metadata
            )
            generation_method = "Template"
        
        logger.info(f"리포트 생성 완료 - 방식: {generation_method}, "
                   f"길이: {len(report_summary)}")
        
    except Exception as e:
        logger.error(f"리포트 생성 중 오류: {str(e)}")
        return {
            "report_summary": None,
            "error_log": (state.error_log or []) + [f"리포트 생성 실패: {str(e)}"]
        }
    
    # ==========================================
    # 3️⃣ 결과 반환 (State 업데이트)
    # ==========================================
    result = {
        "report_summary": report_summary,
        "report_data": {
            "regulation_id": metadata.get("regulation_id"),
            "translation_id": metadata.get("translation_id"),
            "product_ids": list(impact_scores.keys()),
            "country_code": metadata.get("country_code"),
            "generated_at": datetime.utcnow().isoformat(),
            "generation_method": generation_method,
            "high_risk_count": len([s for s in impact_scores.values() if s >= 0.7]),
            "medium_risk_count": len([s for s in impact_scores.values() if 0.3 <= s < 0.7]),
            "low_risk_count": len([s for s in impact_scores.values() if s < 0.3])
        }
    }
    
    logger.info("=== 요약 리포트 생성 노드 완료 ===")
    return result


# ==========================================
# 🔧 헬퍼 함수들
# ==========================================

def _extract_regulation_text(state: AppState) -> str:
    """State에서 규제 텍스트 추출 (우선순위: normalized > original)"""
    return state.normalized_text or state.regulation_text or ""


def _extract_impact_scores(state: AppState) -> Dict[str, float]:
    """State에서 영향도 점수 추출"""
    impact_scores = state.impact_scores or {}
    
    # 타입 변환 (필요 시)
    if isinstance(impact_scores, dict):
        return {str(k): float(v) for k, v in impact_scores.items()}
    
    return {}


def _validate_inputs(
    regulation_text: str, 
    impact_scores: Dict[str, float],
    current_errors: list
) -> Dict[str, Any]:
    """
    입력 데이터 유효성 검증
    
    Returns:
        Dict: {"is_valid": bool, "errors": list}
    """
    errors = list(current_errors)
    
    # 규제 텍스트 검증
    if not regulation_text or len(regulation_text.strip()) < 10:
        errors.append("규제 변경 내용이 없거나 너무 짧습니다")
    
    # 영향도 점수 검증
    if not impact_scores:
        errors.append("영향평가 데이터가 없습니다")
    
    # 점수 범위 검증
    invalid_scores = [
        k for k, v in impact_scores.items() 
        if not (0.0 <= v <= 1.0)
    ]
    if invalid_scores:
        errors.append(f"유효하지 않은 영향도 점수: {invalid_scores[:3]}")
    
    return {
        "is_valid": len(errors) == len(current_errors),  # 새 에러 없음
        "errors": errors
    }


async def _generate_llm_report(
    regulation_text: str,
    impact_scores: Dict[str, float],
    metadata: Dict[str, Any]
) -> str:
    """
    LLM 기반 요약 리포트 생성 (고품질)
    
    Chain을 통해 프롬프트 실행
    """
    chain = ReportGeneratorChain()
    
    try:
        report = await chain.generate(
            regulation_text=regulation_text,
            impact_scores=impact_scores,
            metadata=metadata
        )
        return report
    
    except Exception as e:
        logger.error(f"LLM 호출 실패: {str(e)}")
        # Fallback: Template 방식으로 전환
        logger.info("Template 방식으로 폴백")
        return _generate_template_report(regulation_text, impact_scores, metadata)


def _generate_template_report(
    regulation_text: str,
    impact_scores: Dict[str, float],
    metadata: Dict[str, Any]
) -> str:
    """
    Template 기반 요약 리포트 생성 (빠른 처리)
    
    팩트 중심의 구조화된 리포트
    """
    
    # 영향도별 제품 분류
    high_risk = [pid for pid, score in impact_scores.items() if score >= 0.7]
    medium_risk = [pid for pid, score in impact_scores.items() if 0.3 <= score < 0.7]
    low_risk = [pid for pid, score in impact_scores.items() if score < 0.3]
    
    # 규제 텍스트 요약 (첫 300자)
    regulation_summary = regulation_text[:300].strip() + "..."
    
    # 템플릿 생성
    report = f"""# 규제 변경 요약 리포트

## 📋 규제 변경 개요
{regulation_summary}

## 🌍 규제 정보
- **국가**: {metadata.get('country_code', 'N/A')}
- **시행일**: {metadata.get('effective_date', 'N/A')}
- **규제 ID**: {metadata.get('regulation_id', 'N/A')}

## 📊 영향도 분석 결과

### 🔴 고위험 제품 ({len(high_risk)}개)
영향도 점수 0.7 이상 - **즉시 대응 필요**
{_format_product_list(high_risk, impact_scores, limit=5)}

### 🟡 중위험 제품 ({len(medium_risk)}개)
영향도 점수 0.3~0.7 - 모니터링 필요
{_format_product_list(medium_risk, impact_scores, limit=3)}

### 🟢 저위험 제품 ({len(low_risk)}개)
영향도 점수 0.3 미만 - 영향 미미

## 📌 권장 조치사항

1. **즉시 조치 (고위험 제품)**
   - 고위험 제품에 대한 상세 규제 분석 수행
   - 제품별 대응 전략 수립 및 시뮬레이션
   - 법무팀 및 품질팀과 긴급 협의

2. **단기 조치 (중위험 제품)**
   - 규제 변경 사항 모니터링
   - 필요 시 제품 사양 검토

3. **장기 모니터링**
   - 관련 규제 동향 지속 추적
   - 분기별 영향도 재평가

***
*본 리포트는 자동 생성되었습니다. 상세 분석은 담당 부서와 협의하시기 바랍니다.*
"""
    
    return report.strip()


def _format_product_list(
    product_ids: list, 
    impact_scores: Dict[str, float], 
    limit: int = 5
) -> str:
    """제품 목록을 포맷팅된 텍스트로 변환"""
    
    if not product_ids:
        return "- 해당 없음"
    
    # 점수 높은 순으로 정렬
    sorted_products = sorted(
        product_ids, 
        key=lambda pid: impact_scores[pid], 
        reverse=True
    )
    
    lines = []
    for pid in sorted_products[:limit]:
        score = impact_scores[pid]
        lines.append(f"- 제품 ID: {pid} (영향도: {score:.3f})")
    
    if len(product_ids) > limit:
        lines.append(f"- ... 외 {len(product_ids) - limit}개")
    
    return "\n".join(lines)


# ==========================================
# 🧪 테스트용 (개발 중)
# ==========================================

if __name__ == "__main__":
    """로컬 테스트용 코드"""
    import asyncio
    
    async def test_report_node():
        # 테스트 State 생성
        test_state = AppState(
            regulation_text="담배 니코틴 함량 규제가 1.2mg에서 0.9mg으로 강화됩니다.",
            impact_scores={
                "product_001": 0.85,
                "product_002": 0.45,
                "product_003": 0.15
            },
            metadata={
                "country_code": "US",
                "effective_date": "2026-01-01",
                "regulation_id": 12345,
                "use_llm": False  # Template 테스트
            }
        )
        
        # 노드 실행
        result = await report_node(test_state)
        
        print("=== 테스트 결과 ===")
        print(result.get("report_summary"))
        print("\n=== 메타데이터 ===")
        print(result.get("report_data"))
    
    # 실행
    asyncio.run(test_report_node())