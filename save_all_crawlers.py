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

# import asyncio
# from sqlalchemy import text
# from app.core.database import AsyncSessionLocal, engine, Base
# import app.core.models.regulation_model 

# # [Import] 크롤러들
# from app.crawler.crawling_regulation.usa_fda import USAFDACrawler
# from app.crawler.crawling_regulation.california_law import CaliforniaLawCrawler
# from app.crawler.crawling_regulation.sf_bos_selenium import SFBOSSeleniumCrawler
# from app.crawler.crawling_regulation.ecfr_api import ECFRAPICrawler
# from app.crawler.crawling_regulation.russia_eec import RussiaEECCrawler  # [신규 추가]

# from app.core.repositories.crawl_repository import CrawlRepository

# async def init_seed_data(db):
#     print("⚙️ 기초 데이터(Seed) 점검 중...")
#     try:
#         # 국가 코드 추가 (RU)
#         for code, name in [('US', 'United States'), ('RU', 'Russia')]:
#             if not (await db.execute(text(f"SELECT 1 FROM countries WHERE country_code = '{code}'"))).scalar():
#                 await db.execute(text(f"INSERT INTO countries (country_code, country_name) VALUES ('{code}', '{name}')"))
        
#         # 데이터 소스 추가 (ID 5: Russia EEC)
#         sources = [
#             (1, 'US FDA', 'https://www.fda.gov', 'html'),
#             (2, 'CA Legislature', 'https://leginfo.legislature.ca.gov', 'html'),
#             (3, 'San Francisco BOS', 'https://sfbos.org', 'html'),
#             (4, 'eCFR API', 'https://www.ecfr.gov', 'api'),
#             (5, 'Eurasian Economic Commission', 'https://eec.eaeunion.org', 'html') # [신규]
#         ]
        
#         for s_id, s_name, s_url, s_type in sources:
#             if not (await db.execute(text(f"SELECT 1 FROM data_sources WHERE source_id = {s_id}"))).scalar():
#                 print(f"   + 소스 추가: {s_name}")
#                 await db.execute(text(f"INSERT INTO data_sources (source_id, source_name, url, source_type) VALUES ({s_id}, '{s_name}', '{s_url}', '{s_type}')"))
        
#         await db.commit()
#         print("✅ 기초 데이터 준비 완료")
#     except Exception as e:
#         print(f"⚠️ 기초 데이터 생성 중 경고: {e}")
#         await db.rollback()

# async def run_single_crawler(crawler_instance, source_name):
#     print(f"\n🚀 [{source_name}] 크롤링 시작...")
#     crawler = crawler_instance
#     try:
#         data_list = await crawler.run()
#         print(f"📦 [{source_name}] 수집된 데이터: {len(data_list)}건")

#         if not data_list:
#             print(f"⚠️ [{source_name}] 데이터 없음. 스킵합니다.")
#             return

#         async with AsyncSessionLocal() as db:
#             service = CrawlRepository(db)
#             success, skipped, errors = 0, 0, 0

#             print(f"💾 [{source_name}] 저장 및 분석 중...")
#             for data in data_list:
#                 try:
#                     # [eCFR 예외 처리] eCFR은 파일 다운로드 시 404 이슈가 있으므로 크롤러 인자를 넘기지 않음 (메타데이터만 저장)
#                     if "eCFR" in source_name:
#                         result = await service.process_crawled_data(data, crawler=None) # 파일 다운로드 Skip
#                     else:
#                         result = await service.process_crawled_data(data, crawler) # 파일 다운로드 진행
                    
#                     if result == "skipped": skipped += 1
#                     else: success += 1
#                 except Exception as e:
#                     print(f"❌ 저장 실패: {e}")
#                     errors += 1
#                     await db.rollback()
            
#             print(f"📊 [{source_name}] 결과: 성공 {success} / 스킵 {skipped} / 에러 {errors}")

#     except Exception as e:
#         print(f"❌ [{source_name}] 크롤러 치명적 오류: {e}")
#     finally:
#         await crawler.close()

# async def main():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)

#     async with AsyncSessionLocal() as db:
#         await init_seed_data(db)

#     # [실행 목록]
#     crawlers_to_run = [
#         # (USAFDACrawler(), "US FDA"),
#         # (CaliforniaLawCrawler(), "California Law"),
#         # (SFBOSSeleniumCrawler(), "SF Board of Supervisors"),
#         # (ECFRAPICrawler(title_number="21", query="tobacco"), "eCFR Title 21 (FDA)"),
        
#         # [신규] 러시아 크롤러 단독 테스트
#         (RussiaEECCrawler(), "Russia EAEU TR"),
#     ]

#     print("\n" + "="*50)
#     print("🌍 글로벌 규제 통합 수집 시작")
#     print("="*50)

#     for crawler_instance, name in crawlers_to_run:
#         await run_single_crawler(crawler_instance, name)
#         await asyncio.sleep(2)

#     print("\n" + "="*50)
#     print("🎉 모든 크롤링 작업 완료!")
#     print("="*50)
#     await engine.dispose()

# if __name__ == "__main__":
#     asyncio.run(main())


# import asyncio
# from sqlalchemy import text
# from app.core.database import AsyncSessionLocal, engine, Base
# import app.core.models.regulation_model 

# # [1] 모든 크롤러 임포트
# from app.crawler.crawling_regulation.usa_fda import USAFDACrawler
# from app.crawler.crawling_regulation.california_law import CaliforniaLawCrawler
# from app.crawler.crawling_regulation.sf_bos_selenium import SFBOSSeleniumCrawler # Selenium 버전 사용
# from app.crawler.crawling_regulation.ecfr_api import ECFRAPICrawler # [추가]

# from app.core.repositories.crawl_repository import CrawlRepository

# async def init_seed_data(db):
#     """국가 및 데이터 소스 기초 데이터 생성"""
#     print("⚙️ 기초 데이터(Seed) 점검 중...")
#     try:
#         # 1. 국가 코드 (US)
#         if not (await db.execute(text("SELECT 1 FROM countries WHERE country_code = 'US'"))).scalar():
#             await db.execute(text("INSERT INTO countries (country_code, country_name) VALUES ('US', 'United States')"))
        
#         # 2. 데이터 소스 (ID 1: FDA, 2: CA, 3: SF, 4: eCFR)
#         sources = [
#             (1, 'US FDA', 'https://www.fda.gov', 'html'),
#             (2, 'CA Legislature', 'https://leginfo.legislature.ca.gov', 'html'),
#             (3, 'San Francisco BOS', 'https://sfbos.org', 'html'),
#             (4, 'eCFR API', 'https://www.ecfr.gov', 'api') # ID 4번 추가
#         ]
        
#         for s_id, s_name, s_url, s_type in sources:
#             if not (await db.execute(text(f"SELECT 1 FROM data_sources WHERE source_id = {s_id}"))).scalar():
#                 print(f"   + 소스 추가: {s_name}")
#                 await db.execute(text(f"INSERT INTO data_sources (source_id, source_name, url, source_type) VALUES ({s_id}, '{s_name}', '{s_url}', '{s_type}')"))
        
#         await db.commit()
#         print("✅ 기초 데이터 준비 완료")
#     except Exception as e:
#         print(f"⚠️ 기초 데이터 생성 중 경고: {e}")
#         await db.rollback()

# # [수정됨] crawler_cls가 아니라 crawler_instance를 받도록 변경
# async def run_single_crawler(crawler_instance, source_name):
#     """단일 크롤러 실행 및 저장 로직"""
#     print(f"\n🚀 [{source_name}] 크롤링 시작...")
    
#     # [수정됨] 이미 밖에서 생성된 객체를 그대로 사용합니다.
#     crawler = crawler_instance 
    
#     try:
#         # 1. 데이터 수집
#         data_list = await crawler.run()
#         print(f"📦 [{source_name}] 수집된 데이터: {len(data_list)}건")

#         if not data_list:
#             print(f"⚠️ [{source_name}] 데이터 없음. 스킵합니다.")
#             return

#         # 2. DB 저장 및 처리
#         async with AsyncSessionLocal() as db:
#             service = CrawlRepository(db)
            
#             success = 0
#             skipped = 0
#             errors = 0

#             print(f"💾 [{source_name}] 저장 및 분석 중...")
#             for data in data_list:
#                 try:
#                     result = await service.process_crawled_data(data, crawler)
#                     if result == "skipped": skipped += 1
#                     else: success += 1
#                 except Exception as e:
#                     print(f"❌ 저장 실패: {e}")
#                     errors += 1
#                     await db.rollback()
            
#             print(f"📊 [{source_name}] 결과: 성공 {success} / 스킵 {skipped} / 에러 {errors}")

#     except Exception as e:
#         print(f"❌ [{source_name}] 크롤러 치명적 오류: {e}")
#     finally:
#         # [중요] 세션 종료는 여기서 수행
#         await crawler.close()

# async def main():
#     # 1. 테이블 생성
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)

#     # 2. 기초 데이터 초기화
#     async with AsyncSessionLocal() as db:
#         await init_seed_data(db)

#     # [3] 실행할 크롤러 목록 정의 (모두 인스턴스로 생성해서 넣음)
#     crawlers_to_run = [
#         (USAFDACrawler(), "US FDA"), # 괄호 () 추가!
#         (CaliforniaLawCrawler(), "California Law"), # 괄호 () 추가!
#         (SFBOSSeleniumCrawler(), "SF Board of Supervisors"), # 괄호 () 추가!
#         # eCFR은 파라미터가 필요하므로 이미 인스턴스 상태임
#         (ECFRAPICrawler(title_number="21", query="tobacco"), "eCFR Title 21 (FDA)"),
#         (ECFRAPICrawler(title_number="27", query="tobacco"), "eCFR Title 27 (ATF)"),
#     ]

#     # 4. 순차 실행
#     print("\n" + "="*50)
#     print("🌍 글로벌 규제 통합 수집 시작")
#     print("="*50)

#     for crawler_instance, name in crawlers_to_run:
#         await run_single_crawler(crawler_instance, name)
#         # 다음 사이트 넘어가기 전 잠깐 대기
#         await asyncio.sleep(2) 

#     print("\n" + "="*50)
#     print("🎉 모든 크롤링 작업 완료!")
#     print("="*50)
#     await engine.dispose()

# if __name__ == "__main__":
#     asyncio.run(main())



# import asyncio
# from sqlalchemy import text
# from app.core.database import AsyncSessionLocal, engine, Base
# import app.core.models.regulation_model 

# # [1] 모든 크롤러 임포트
# from app.crawler.crawling_regulation.usa_fda import USAFDACrawler
# from app.crawler.crawling_regulation.california_law import CaliforniaLawCrawler
# from app.crawler.crawling_regulation.sf_bos_selenium import SFBOSSeleniumCrawler # Selenium 버전 사용
# from app.crawler.crawling_regulation.ecfr_api import ECFRAPICrawler # [추가]


# from app.core.repositories.crawl_repository import CrawlRepository

# async def init_seed_data(db):
#     """국가 및 데이터 소스 기초 데이터 생성"""
#     print("⚙️ 기초 데이터(Seed) 점검 중...")
#     try:
#         # 1. 국가 코드 (US)
#         if not (await db.execute(text("SELECT 1 FROM countries WHERE country_code = 'US'"))).scalar():
#             await db.execute(text("INSERT INTO countries (country_code, country_name) VALUES ('US', 'United States')"))
        
#         # 2. 데이터 소스 (ID 1: FDA, 2: CA, 3: SF)
#         sources = [
#             (1, 'US FDA', 'https://www.fda.gov', 'html'),
#             (2, 'CA Legislature', 'https://leginfo.legislature.ca.gov', 'html'),
#             (3, 'San Francisco BOS', 'https://sfbos.org', 'html'),
#             # 4. eCFR API 소스 추가
#             (4, 'eCFR API (Title 21)', 'https://www.ecfr.gov', 'api')
#         ]
        
#         for s_id, s_name, s_url, s_type in sources:
#             if not (await db.execute(text(f"SELECT 1 FROM data_sources WHERE source_id = {s_id}"))).scalar():
#                 print(f"   + 소스 추가: {s_name}")
#                 await db.execute(text(f"INSERT INTO data_sources (source_id, source_name, url, source_type) VALUES ({s_id}, '{s_name}', '{s_url}', '{s_type}')"))
        
#         await db.commit()
#         print("✅ 기초 데이터 준비 완료")
#     except Exception as e:
#         print(f"⚠️ 기초 데이터 생성 중 경고: {e}")
#         await db.rollback()

# async def run_single_crawler(crawler_cls, source_name):
#     """단일 크롤러 실행 및 저장 로직"""
#     print(f"\n🚀 [{source_name}] 크롤링 시작...")
    
#     crawler = crawler_cls() # 크롤러 인스턴스 생성
    
#     try:
#         # 1. 데이터 수집
#         data_list = await crawler.run()
#         print(f"📦 [{source_name}] 수집된 데이터: {len(data_list)}건")

#         if not data_list:
#             print(f"⚠️ [{source_name}] 데이터 없음. 스킵합니다.")
#             return

#         # 2. DB 저장 및 처리
#         async with AsyncSessionLocal() as db:
#             service = CrawlRepository(db)
            
#             success = 0
#             skipped = 0
#             errors = 0

#             print(f"💾 [{source_name}] 저장 및 분석 중...")
#             for data in data_list:
#                 try:
#                     # CrawlRepository가 알아서 url로 중복 체크 및 다운로드를 수행합니다.
#                     result = await service.process_crawled_data(data, crawler)
#                     if result == "skipped": skipped += 1
#                     else: success += 1
#                 except Exception as e:
#                     print(f"❌ 저장 실패: {e}")
#                     errors += 1
#                     await db.rollback()
            
#             print(f"📊 [{source_name}] 결과: 성공 {success} / 스킵 {skipped} / 에러 {errors}")

#     except Exception as e:
#         print(f"❌ [{source_name}] 크롤러 치명적 오류: {e}")
#     finally:
#         await crawler.close()

# async def main():
#     # 1. 테이블 생성
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)

#     # 2. 기초 데이터 초기화
#     async with AsyncSessionLocal() as db:
#         await init_seed_data(db)

#     # [3] 실행할 크롤러 목록 정의
#     # (클래스명, 표시이름) 튜플 리스트
#     crawlers_to_run = [
#         (USAFDACrawler, "US FDA"),
#         (CaliforniaLawCrawler, "California Law"),
#         (SFBOSSeleniumCrawler, "SF Board of Supervisors"),
#         # [신규] eCFR API 크롤러 (Title 21 - FDA 관련)
#         (ECFRAPICrawler(title_number="21", query="tobacco"), "eCFR Title 21 (FDA)"),
        
#         # [신규] eCFR API 크롤러 (Title 27 - ATF/TTB 관련)
#         (ECFRAPICrawler(title_number="27", query="tobacco"), "eCFR Title 27 (ATF)"),
#     ]

#     # 4. 순차 실행
#     print("\n" + "="*50)
#     print("🌍 글로벌 규제 통합 수집 시작")
#     print("="*50)

#     for crawler_cls, name in crawlers_to_run:
#         await run_single_crawler(crawler_cls, name)
#         # 다음 사이트 넘어가기 전 잠깐 대기 (선택사항)
#         await asyncio.sleep(2) 

#     print("\n" + "="*50)
#     print("🎉 모든 크롤링 작업 완료!")
#     print("="*50)
#     await engine.dispose()

# if __name__ == "__main__":
#     asyncio.run(main())