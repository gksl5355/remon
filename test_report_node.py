

"""
report_node 단독 테스트 스크립트
더미 데이터를 수동으로 주입하여 요약 리포트 생성 테스트

실행 방법:
python test_report_node.py
"""

import asyncio
import os
from dotenv import load_dotenv
from app.ai_pipeline.state import AppState
from app.ai_pipeline.nodes.report import report_node


# .env 파일 로드
load_dotenv()

# OpenAI API 키 확인
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("❌ 오류: OPENAI_API_KEY가 .env 파일에 없습니다!")
    print("💡 .env 파일에 다음을 추가하세요:")
    print("OPENAI_API_KEY=sk-...")
    exit(1)

print(f"✅ OpenAI API 키 확인 완료: {api_key[:10]}...")


# ==========================================
# 🧪 더미 데이터 생성
# ==========================================

def create_dummy_state():
    """
    테스트용 더미 State 생성
    
    규제 변경 내역 + 영향평가 데이터를 수동으로 주입
    """
    
    # 📋 더미 규제 변경 내역
    dummy_regulation = """
    미국 FDA(식품의약국)는 2026년 1월 1일부터 담배 제품의 니코틴 함량 
    상한선을 현행 1.2mg에서 0.9mg으로 강화한다고 발표했습니다.
    
    이번 규제는 미국 내 흡연율을 낮추기 위한 연방 정책의 일환으로, 
    모든 담배 제조사는 2025년 12월 31일까지 제품 재설계를 완료해야 합니다.
    
    주요 변경 사항:
    - 니코틴 함량: 1.2mg → 0.9mg (25% 감소)
    - 시행일: 2026년 1월 1일
    - 준수 기한: 2025년 12월 31일
    - 위반 시: 제품 판매 금지 및 벌금 부과
    
    FDA는 이번 규제가 연간 약 5만 명의 흡연 관련 사망자를 줄일 것으로 
    예상하고 있으며, 특히 청소년 흡연율에 긍정적 영향을 미칠 것으로 
    전망하고 있습니다.
    """
    
    # 📊 더미 영향평가 데이터 (제품별 영향도 점수)
    dummy_impact_scores = {
        "product_001": 0.95,  # 고위험 (니코틴 함량 1.5mg)
        "product_002": 0.88,  # 고위험 (니코틴 함량 1.3mg)
        "product_003": 0.82,  # 고위험 (니코틴 함량 1.2mg)
        "product_004": 0.65,  # 중위험 (니코틴 함량 1.0mg)
        "product_005": 0.48,  # 중위험 (니코틴 함량 0.95mg)
        "product_006": 0.25,  # 저위험 (니코틴 함량 0.85mg)
        "product_007": 0.12,  # 저위험 (니코틴 함량 0.7mg)
        "product_008": 0.08,  # 저위험 (니코틴 함량 0.6mg)
    }
    
    # 🌍 더미 메타데이터
    dummy_metadata = {
        "country_code": "US",
        "effective_date": "2026-01-01",
        "regulation_id": 98765,
        "translation_id": 12345,
        "use_llm": True,  # LLM 사용 (False면 Template만 사용)
    }
    
    # AppState 생성
    state = AppState(
        regulation_text=dummy_regulation,
        normalized_text=dummy_regulation,  # 전처리 완료 상태 가정
        impact_scores=dummy_impact_scores,
        metadata=dummy_metadata,
        error_log=[]
    )
    
    return state


# ==========================================
# 🚀 테스트 실행
# ==========================================

async def test_report_generation():
    """
    report_node 테스트 실행
    """
    
    print("\n" + "="*60)
    print("🧪 요약 리포트 생성 테스트 시작")
    print("="*60 + "\n")
    
    # 1️⃣ 더미 State 생성
    print("📦 1단계: 더미 데이터 생성 중...")
    test_state = create_dummy_state()
    
    print(f"   ✅ 규제 텍스트: {len(test_state.regulation_text)} 문자")
    print(f"   ✅ 영향평가 제품 수: {len(test_state.impact_scores)}개")
    print(f"   ✅ 국가: {test_state.metadata['country_code']}")
    print(f"   ✅ LLM 사용: {test_state.metadata['use_llm']}")
    
    # 2️⃣ report_node 실행
    print("\n📝 2단계: 요약 리포트 생성 중...")
    print("   (OpenAI API 호출 중 - 10~30초 소요)\n")
    
    try:
        result = await report_node(test_state)
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        return
    
    # 3️⃣ 결과 확인
    print("\n" + "="*60)
    print("✅ 요약 리포트 생성 완료!")
    print("="*60 + "\n")
    
    # 리포트 내용 출력
    if result.get("report_summary"):
        print("📄 생성된 요약 리포트:")
        print("-"*60)
        print(result["report_summary"])
        print("-"*60)
    else:
        print("❌ 리포트 생성 실패")
        if result.get("error_log"):
            print(f"오류 로그: {result['error_log']}")
    
    # 메타데이터 출력
    if result.get("report_data"):
        print("\n📊 리포트 메타데이터:")
        for key, value in result["report_data"].items():
            print(f"   - {key}: {value}")
    
    print("\n" + "="*60)
    print("🎉 테스트 완료!")
    print("="*60 + "\n")


# ==========================================
# 🎬 메인 실행
# ==========================================

if __name__ == "__main__":
    """
    테스트 실행
    
    실행 방법:
    python test_report_node.py
    """
    
    # 비동기 실행
    asyncio.run(test_report_generation())
