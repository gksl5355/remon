#!/usr/bin/env python
"""
KTNG 전략 데이터를 skala-2.4.17-strategy 컬렉션에 임베딩
updated: 2025-01-19

Usage:
    uv run python scripts/embed_ktng_strategies.py
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from app.ai_pipeline.tools.strategy_history import StrategyHistoryTool


# KTNG 데이터 (5개 케이스)
KTNG_CASES = [
    {
        "case_id": "S001",
        "regulation_text": "Nicotine concentration must not exceed 20mg/mL.",
        "strategy": "니코틴 원액 투입 비율을 18mg/mL 수준으로 조정하는 포뮬러 재설계 진행. 제조라인의 니코틴 자동 투입 장비 교정 작업 수행. 점도·증기량·타격감 등 주요 품질 항목에 대한 단기 안정성 테스트 반복 수행. 초과 농도 제품 재고는 규제 리스크 방지를 위해 회수 및 폐기 조치 진행.",
        "products": ["VapeX Mint 20mg", "TobaccoPure Classic 20mg"],
        "country": "US"
    },
    {
        "case_id": "S002",
        "regulation_text": "Warning labels must cover at least 50% of the packaging.",
        "strategy": "경고문 50% 기준을 충족하는 신규 패키지 템플릿 제작 진행. 외부 인쇄업체와 협력하여 전체 SKU 패키지 재인쇄 작업 수행. 물류센터에서 구형 패키지 전량 회수 및 폐기 처리 진행. 패키지 버전 관리를 자동화하기 위한 ERP 업데이트 작업 수행.",
        "products": ["CloudHit Berry 15mg", "VapeX Mint 20mg"],
        "country": "US"
    },
    {
        "case_id": "S003",
        "regulation_text": "Flavored nicotine liquids except tobacco flavor are prohibited.",
        "strategy": "향료 기반 제품군 판매 중단 조치 진행. 타바코향 대체 포뮬러 개발 프로젝트를 단기 일정으로 추진. 유통 채널에 flavor 제품 회수 안내 및 반품 절차 전달. flavor-free 제품으로 전환을 위한 마케팅 캠페인 기획 및 적용 진행.",
        "products": ["CloudHit Berry 15mg", "VapeX Mint 20mg"],
        "country": "US"
    },
    {
        "case_id": "S004",
        "regulation_text": "Online advertisements must include visible health disclaimers.",
        "strategy": "디지털 광고 템플릿에 표준 건강 경고문 삽입 작업 적용. 광고 업로드 과정에 경고문 누락 검출 자동 검수 스크립트 연동 수행. 긴급 게시 필요 콘텐츠는 수동 편집 후 우선 게시 진행.",
        "products": ["VapeX Mint 20mg"],
        "country": "US"
    },
    {
        "case_id": "S005",
        "regulation_text": "Retailers must report monthly sales statistics.",
        "strategy": "POS 데이터를 ERP와 연동하는 월별 판매 데이터 자동 집계 프로세스 구축 진행. 규제기관 제출 양식에 맞춘 자동 보고서 생성 기능 적용. 제출 전 관리자 검수 단계를 포함하여 데이터 정확성 확보 절차 수행.",
        "products": ["TobaccoPure Classic 20mg", "CloudHit Berry 15mg"],
        "country": "US"
    }
]


def main():
    print("=" * 60)
    print("🚀 KTNG 전략 데이터 임베딩")
    print("=" * 60)
    print(f"컬렉션: skala-2.4.17-strategy")
    print(f"데이터: {len(KTNG_CASES)}개 케이스")
    print()
    
    # StrategyHistoryTool 초기화
    tool = StrategyHistoryTool(collection="skala-2.4.17-strategy")
    
    # 컬렉션 생성 (없으면)
    print("📦 컬렉션 확인 중...")
    tool.ensure_collection()
    print("✅ 컬렉션 준비 완료")
    print()
    
    # 각 케이스 임베딩
    for i, case in enumerate(KTNG_CASES, 1):
        print(f"[{i}/{len(KTNG_CASES)}] {case['case_id']} 처리 중...")
        print(f"   규제: {case['regulation_text'][:60]}...")
        print(f"   제품: {', '.join(case['products'])}")
        
        try:
            # 전략을 리스트로 변환 (단일 전략이므로 1개 항목)
            strategies = [case['strategy']]
            
            tool.save_strategy_history(
                regulation_summary=case['regulation_text'],
                mapped_products=case['products'],
                strategies=strategies
            )
            
            print(f"   ✅ 저장 완료")
        except Exception as e:
            print(f"   ❌ 실패: {e}")
        
        print()
    
    print("=" * 60)
    print("✅ 임베딩 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
