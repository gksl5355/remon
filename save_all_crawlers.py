import asyncio
import yaml
import os
import sys
from sqlalchemy import text
from dotenv import load_dotenv  # [추가] .env 로드용

from app.core.database import AsyncSessionLocal, engine, Base
from app.crawler.discovery_agent import DiscoveryAgent

# 1. 환경 변수 로드 (.env 파일)
load_dotenv()

def load_config():
    """
    설정 파일 로드
    우선순위: app/config/config.yaml -> (없으면) 현재 폴더의 config.yaml
    """
    base_dir = os.getcwd() # 현재 실행 경로
    
    # 1순위: app/config/config.yaml (권장)
    config_path = os.path.join(base_dir, "app", "config", "config.yaml")
    
    if not os.path.exists(config_path):
        print(f"⚠️ 'app/config/config.yaml'을 찾을 수 없습니다.")
        # 비상용: 루트에 있는 경우 체크
        if os.path.exists("config.yaml"):
             config_path = "config.yaml"
        else:
            return {"targets": []}
    
    print(f"⚙️ 설정 파일 로드: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

async def init_seed_data(db, targets):
    """기초 데이터(국가, 소스) 동기화"""
    print("⚙️ 기초 데이터(Seed) 동기화 중...")
    try:
        # 1. 국가 코드 자동 등록
        for target in targets:
            code = target.get("code")
            name = target.get("country")
            if code and name:
                exists = (await db.execute(text(f"SELECT 1 FROM countries WHERE country_code = '{code}'"))).scalar()
                if not exists:
                    print(f" 🏳️ 신규 국가 등록: {name} ({code})")
                    await db.execute(text(f"INSERT INTO countries (country_code, country_name) VALUES ('{code}', '{name}')"))
        
        # 2. Discovery Agent용 소스 등록 (ID 99)
        if not (await db.execute(text("SELECT 1 FROM data_sources WHERE source_id = 99"))).scalar():
             await db.execute(text("INSERT INTO data_sources (source_id, source_name, url, source_type) VALUES (99, 'Tavily Discovery', 'https://tavily.com', 'ai_search')"))

        await db.commit()
        print("✅ 기초 데이터 준비 완료")
    except Exception as e:
        print(f"⚠️ 기초 데이터 동기화 실패: {e}")
        await db.rollback()

async def main():
    # 1. DB 초기화
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Config 및 API Key 로드
    config = load_config()
    targets = config.get("targets", [])
    
    # [수정] .env에서 API 키 가져오기
    tavily_key = os.getenv("TAVILY_API_KEY")

    if not tavily_key:
        print("🚨 오류: .env 파일에 'TAVILY_API_KEY'가 설정되지 않았습니다.")
        print("   -> .env 파일을 확인하거나 환경 변수를 설정해주세요.")
        return # 키가 없으면 실행 중단 (Mock 모드 원하면 이 줄 주석 처리)

    # 3. Seed 데이터 준비
    async with AsyncSessionLocal() as db:
        await init_seed_data(db, targets)

    print("\n" + "="*60)
    print("🌍 [Global Regulation Monitor] Tavily 기반 감시 시작")
    print(f"🎯 감시 대상: {len([t for t in targets if t['enabled']])}개국")
    print("="*60)

    # 4. 에이전트 실행
    async with AsyncSessionLocal() as db_session:
        # Agent 초기화 (DB세션과 API키 주입)
        agent = DiscoveryAgent(db_session, tavily_api_key=tavily_key)

        for target in targets:
            if not target.get("enabled", False):
                continue
            
            country = target["country"]
            keywords = target["keywords"]
             # [추가] config.yaml에서 category 읽기 (기본값 regulation)
            category = target.get("category", "regulation")

            print(f"\n📡 [{country}] 탐색 시작 ({category})")
            
            # run 함수에 category 전달
            await agent.run(country, keywords, category=category)
            
            await asyncio.sleep(2)

            # print(f"\n📡 [{country}] 규제 탐색 시작 (Keywords: {len(keywords)}개)")
            
            # # Agent가 알아서 검색 -> 판단 -> 다운로드 -> 저장 수행
            # await agent.run(country, keywords)
            
            # # API 호출 속도 조절 (무료 티어 보호)
            # await asyncio.sleep(2)

    print("\n" + "="*60)
    print("🎉 모든 모니터링 작업 완료!")
    print("="*60)
    await engine.dispose()

if __name__ == "__main__":
    # 실행 시 프로젝트 루트 경로를 path에 추가
    sys.path.append(os.getcwd())
    asyncio.run(main())

