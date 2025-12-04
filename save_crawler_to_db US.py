import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal, engine, Base

# [중요] 테이블 생성을 위해 모델을 로드해야 합니다.
# 사용자가 알려준 파일명(regulation_model.py)에 맞게 임포트
import app.core.models.regulation_model 

from app.crawler.usa_fda import USAFDACrawler
from app.services.regulation_service import RegulationService

async def main():
    print("🛠️ 시스템 초기화 중...")

    # 1. DB 테이블 생성 (테이블이 없을 경우 자동 생성)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. 기초 데이터(Seed Data) 생성 - FK 에러 방지용
    # 규제를 저장하려면 '국가 코드(US)'와 '데이터 소스 ID(1)'가 미리 DB에 있어야 합니다.
    async with AsyncSessionLocal() as db:
        try:
            # 2-1. 국가 코드 'US' 확인 및 생성
            result = await db.execute(text("SELECT 1 FROM countries WHERE country_code = 'US'"))
            if not result.scalar():
                print("⚙️ 기초 데이터 생성: Country (US)")
                await db.execute(text("INSERT INTO countries (country_code, country_name) VALUES ('US', 'United States')"))

            # 2-2. 데이터 소스 'ID=1' 확인 및 생성
            result = await db.execute(text("SELECT 1 FROM data_sources WHERE source_id = 1"))
            if not result.scalar():
                print("⚙️ 기초 데이터 생성: DataSource (ID=1)")
                await db.execute(text("INSERT INTO data_sources (source_id, source_name, url, source_type) VALUES (1, 'US FDA', 'https://www.fda.gov', 'html')"))
            
            await db.commit()
        except Exception as e:
            print(f"⚠️ 기초 데이터 생성 중 경고: {e}")
            await db.rollback()

    # 3. 크롤러 초기화 및 실행
    crawler = USAFDACrawler()
    print("🚀 크롤링 작업을 시작합니다...")
    
    try:
        # 데이터 수집 (메타데이터만 먼저 가져옴)
        data_list = await crawler.run()
        print(f"📦 수집된 메타 데이터: {len(data_list)}건")

        if not data_list:
            print("수집된 데이터가 없습니다. 종료합니다.")
            return

        # 4. 서비스 레이어 실행 (DB 저장 + 파일 다운로드 + 전처리)
        async with AsyncSessionLocal() as db:
            service = RegulationService(db)
            
            print("💾 [DB 저장] 및 [파일 다운로드] 파이프라인 가동...")
            
            success_count = 0
            skip_count = 0
            error_count = 0

            for data in data_list:
                try:
                    # [핵심] crawler 인스턴스를 함께 넘겨서, 필요 시 파일을 다운로드하게 함
                    result = await service.process_crawled_data(data, crawler)
                    
                    if result == "skipped":
                        skip_count += 1
                    else:
                        success_count += 1
                        
                except Exception as e:
                    print(f"❌ 처리 실패 ({data.get('title')}): {e}")
                    error_count += 1
                    await db.rollback() # 에러 난 트랜잭션만 롤백하고 계속 진행

            print("\n" + "="*40)
            print(f"✅ 작업 완료 리포트")
            print(f"✨ 처리 성공(신규/업데이트): {success_count}건")
            print(f"⏭️ 변경 없음(Skip): {skip_count}건")
            print(f"❌ 에러: {error_count}건")
            print("="*40)

    except Exception as e:
        print(f"❌ 치명적 오류 발생: {e}")
    finally:
        # 리소스 정리
        await crawler.close()
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())