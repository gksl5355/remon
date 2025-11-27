import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal, engine, Base
import app.core.models.regulation_model 

# [1] 모든 크롤러 임포트
from app.crawler.crawling_regulation.usa_fda import USAFDACrawler
from app.crawler.crawling_regulation.california_law import CaliforniaLawCrawler
from app.crawler.crawling_regulation.sf_bos_selenium import SFBOSSeleniumCrawler # Selenium 버전 사용

from app.core.repositories.crawl_repository import CrawlRepository

async def init_seed_data(db):
    """국가 및 데이터 소스 기초 데이터 생성"""
    print("⚙️ 기초 데이터(Seed) 점검 중...")
    try:
        # 1. 국가 코드 (US)
        if not (await db.execute(text("SELECT 1 FROM countries WHERE country_code = 'US'"))).scalar():
            await db.execute(text("INSERT INTO countries (country_code, country_name) VALUES ('US', 'United States')"))
        
        # 2. 데이터 소스 (ID 1: FDA, 2: CA, 3: SF)
        sources = [
            (1, 'US FDA', 'https://www.fda.gov', 'html'),
            (2, 'CA Legislature', 'https://leginfo.legislature.ca.gov', 'html'),
            (3, 'San Francisco BOS', 'https://sfbos.org', 'html')
        ]
        
        for s_id, s_name, s_url, s_type in sources:
            if not (await db.execute(text(f"SELECT 1 FROM data_sources WHERE source_id = {s_id}"))).scalar():
                print(f"   + 소스 추가: {s_name}")
                await db.execute(text(f"INSERT INTO data_sources (source_id, source_name, url, source_type) VALUES ({s_id}, '{s_name}', '{s_url}', '{s_type}')"))
        
        await db.commit()
        print("✅ 기초 데이터 준비 완료")
    except Exception as e:
        print(f"⚠️ 기초 데이터 생성 중 경고: {e}")
        await db.rollback()

async def run_single_crawler(crawler_cls, source_name):
    """단일 크롤러 실행 및 저장 로직"""
    print(f"\n🚀 [{source_name}] 크롤링 시작...")
    
    crawler = crawler_cls() # 크롤러 인스턴스 생성
    
    try:
        # 1. 데이터 수집
        data_list = await crawler.run()
        print(f"📦 [{source_name}] 수집된 데이터: {len(data_list)}건")

        if not data_list:
            print(f"⚠️ [{source_name}] 데이터 없음. 스킵합니다.")
            return

        # 2. DB 저장 및 처리
        async with AsyncSessionLocal() as db:
            service = CrawlRepository(db)
            
            success = 0
            skipped = 0
            errors = 0

            print(f"💾 [{source_name}] 저장 및 분석 중...")
            for data in data_list:
                try:
                    # CrawlRepository가 알아서 url로 중복 체크 및 다운로드를 수행합니다.
                    result = await service.process_crawled_data(data, crawler)
                    if result == "skipped": skipped += 1
                    else: success += 1
                except Exception as e:
                    print(f"❌ 저장 실패: {e}")
                    errors += 1
                    await db.rollback()
            
            print(f"📊 [{source_name}] 결과: 성공 {success} / 스킵 {skipped} / 에러 {errors}")

    except Exception as e:
        print(f"❌ [{source_name}] 크롤러 치명적 오류: {e}")
    finally:
        await crawler.close()

async def main():
    # 1. 테이블 생성
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. 기초 데이터 초기화
    async with AsyncSessionLocal() as db:
        await init_seed_data(db)

    # [3] 실행할 크롤러 목록 정의
    # (클래스명, 표시이름) 튜플 리스트
    crawlers_to_run = [
        (USAFDACrawler, "US FDA"),
        (CaliforniaLawCrawler, "California Law"),
        (SFBOSSeleniumCrawler, "SF Board of Supervisors"),
    ]

    # 4. 순차 실행
    print("\n" + "="*50)
    print("🌍 글로벌 규제 통합 수집 시작")
    print("="*50)

    for crawler_cls, name in crawlers_to_run:
        await run_single_crawler(crawler_cls, name)
        # 다음 사이트 넘어가기 전 잠깐 대기 (선택사항)
        await asyncio.sleep(2) 

    print("\n" + "="*50)
    print("🎉 모든 크롤링 작업 완료!")
    print("="*50)
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())