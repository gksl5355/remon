import asyncio
import os
import sys
from dotenv import load_dotenv

# 경로 설정
sys.path.append(os.getcwd())
from app.crawler.discovery_agent import DiscoveryAgent
from app.core.database import AsyncSessionLocal, engine, Base

# 환경변수 로드
load_dotenv()

async def run_test():
    print("🧪 [통합 테스트] Tavily 검색 -> 다운로드 -> AI 분석")
    
    # 1. API 키 확인
    tavily_key = os.getenv("TAVILY_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not tavily_key or not openai_key:
        print("🚨 .env 파일에 API Key(TAVILY, OPENAI)가 있는지 확인하세요!")
        return

    # 2. DB 초기화 (테스트용)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 3. 에이전트 실행
    async with AsyncSessionLocal() as db_session:
        agent = DiscoveryAgent(db_session, tavily_api_key=tavily_key)
        
        # [테스트 시나리오]
        # 미국 FDA의 최신 담배 규제 문서를 찾아서 -> 다운받고 -> AI가 요약하는지 확인
        target_country = "USA FDA Test"
        keywords = [
            "site:fda.gov tobacco product standard menthol filetype:pdf"
        ]
        
        print(f"\n🚀 '{keywords[0]}' 검색 시작...")
        await agent.run(target_country, keywords, category="regulation")

    print("\n✅ 테스트 완료. 위 로그에 [AI 분석 결과]가 JSON으로 떴나요?")

if __name__ == "__main__":
    asyncio.run(run_test())