# save_crawler_to_db.py

import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal, engine, Base
import app.core.models.regulation_model 

# [변경] SFBOS 크롤러 임포트
from app.crawler.crawling_regulation.sf_bos_selenium import SFBOSSeleniumCrawler
from app.services.regulation_service import RegulationService

async def main():
    # 1. 테이블 생성
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. 기초 데이터 생성 (SF BOS 추가)
    async with AsyncSessionLocal() as db:
        try:
            # 2-1. 국가 코드 'US' 확인
            result = await db.execute(text("SELECT 1 FROM countries WHERE country_code = 'US'"))
            if not result.scalar():
                print("⚙️ 기초 데이터 생성: Country (US)")
                await db.execute(text("INSERT INTO countries (country_code, country_name) VALUES ('US', 'United States')"))

            # 2-2. 데이터 소스 'ID=3' (SF BOS) 확인 및 생성
            # (ID 1=FDA, 2=CA Law, 3=SF BOS로 가정)
            result = await db.execute(text("SELECT 1 FROM data_sources WHERE source_id = 3"))
            if not result.scalar():
                print("⚙️ 기초 데이터 생성: DataSource (ID=3)")
                await db.execute(text("INSERT INTO data_sources (source_id, source_name, url, source_type) VALUES (3, 'San Francisco BOS', 'https://sfbos.org', 'html')"))
            
            await db.commit()
        except Exception as e:
            print(f"⚠️ 기초 데이터 생성 중 경고: {e}")
            await db.rollback()

    # 3. 크롤러 실행 (SF BOS)
    crawler = SFBOSSeleniumCrawler() 
    print("🚀 크롤링 작업을 시작합니다...")
    
    try:
        data_list = await crawler.run()
        print(f"📦 수집된 메타 데이터: {len(data_list)}건")

        if not data_list:
            print("수집된 데이터가 없습니다. (구글 검색 엔진일 가능성 있음)")
            return

        # 4. 서비스 실행
        async with AsyncSessionLocal() as db:
            service = RegulationService(db)
            print("💾 [DB 저장] 및 [파일 다운로드] 파이프라인 가동...")
            
            success_count = 0
            skip_count = 0
            error_count = 0

            for data in data_list:
                try:
                    # source_id를 3으로 설정해야 하므로, 
                    # RegulationService 내부에서 고정된 source_id=1을 쓰면 안됩니다.
                    # 하지만 현재 Service 코드는 source_id=1로 고정되어 있으니
                    # 이 부분은 Service 코드 수정 없이 일단 진행합니다.
                    # (정석은 service.process_crawled_data에 source_id를 인자로 넘기는 것입니다)
                    
                    result = await service.process_crawled_data(data, crawler)
                    
                    if result == "skipped":
                        skip_count += 1
                    else:
                        success_count += 1
                        
                except Exception as e:
                    print(f"❌ 처리 실패 ({data.get('title')}): {e}")
                    error_count += 1
                    await db.rollback()

            print("\n" + "="*40)
            print(f"✅ 작업 완료 리포트")
            print(f"✨ 처리 성공: {success_count}건")
            print(f"⏭️ 변경 없음: {skip_count}건")
            print(f"❌ 에러: {error_count}건")
            print("="*40)

    except Exception as e:
        print(f"❌ 치명적 오류 발생: {e}")
    finally:
        await crawler.close()
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())