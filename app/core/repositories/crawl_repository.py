import os
import aiofiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional

# S3 업로더 및 모델 임포트
from app.utils.s3_uploader import S3Uploader
from app.core.models.regulation_model import Regulation, RegulationVersion, RegulationChangeHistory
from app.crawler.crawling_regulation.base import UniversalFetcher

class CrawlRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.s3_uploader = S3Uploader()
        self.local_backup_dir = "db"

    async def process_crawled_data(self, data: dict, crawler: Optional[UniversalFetcher] = None):
        """
        DiscoveryAgent에서 호출하는 진입점
        """
        should_close_crawler = False
        if not crawler:
            crawler = UniversalFetcher()
            should_close_crawler = True

        try:
            url = data["url"]
            
            # DB 중복 체크
            stmt = (
                select(Regulation)
                .join(RegulationVersion, Regulation.regulation_id == RegulationVersion.regulation_id)
                .where(RegulationVersion.original_uri == url)
                .limit(1)
            )
            result = await self.db.execute(stmt)
            existing_reg = result.scalar_one_or_none()

            if not existing_reg:
                return await self._create_new_regulation(data, crawler)
            else:
                return await self._handle_existing_regulation(existing_reg, data, crawler)
        finally:
            if should_close_crawler:
                await crawler.close()

    async def _upload_and_get_path(self, url: str, hash_value: str, crawler: UniversalFetcher, category: str) -> str:
        """파일 다운로드 후 S3 업로드 (경로 반환은 하지만 DB 저장은 생략됨)"""
        # 1. 파일 다운로드
        content = await crawler.fetch_binary(url)
        if not content:
            return None

        # 2. 확장자 판별
        is_pdf = content.startswith(b'%PDF') or url.lower().endswith(".pdf")
        ext = 'pdf' if is_pdf else 'txt'
        filename = f"{hash_value}.{ext}"

        # 3. S3 업로드 시도
        s3_path = self.s3_uploader.upload_file(content, filename, folder=category)
        
        if s3_path:
            print(f"✅ S3 저장 성공: {s3_path}")
            return s3_path

        # 4. 실패 시 로컬 백업
        print("⚠️ S3 업로드 실패 -> 로컬 백업 진행")
        save_dir = os.path.join(self.local_backup_dir, category)
        os.makedirs(save_dir, exist_ok=True)
        local_path = os.path.join(save_dir, filename)
        
        async with aiofiles.open(local_path, "wb") as f:
            await f.write(content)
            
        return local_path

    async def _create_new_regulation(self, data: dict, crawler: UniversalFetcher):
        category = data.get("category", "regulation")
        
        # 1. 파일 업로드 (S3에는 올라감)
        storage_path = await self._upload_and_get_path(data["url"], data["hash_value"], crawler, category)

        if not storage_path:
            return "failed"

        # 2. Regulation 테이블 저장
        new_reg = Regulation(
            source_id=data.get("source_id", 99),
            country_code=data.get("country_code", "ZZ"),
            title=data.get("title", "No Title"),
            status="active"
        )
        self.db.add(new_reg)
        await self.db.flush()
        
        # 3. RegulationVersion 테이블 저장
        # [수정] file_path 인자 제거 (DB 스키마에 컬럼이 없으므로)
        new_version = RegulationVersion(
            regulation_id=new_reg.regulation_id,
            version_number=1,
            original_uri=data["url"],
            # file_path=storage_path,  <-- [삭제됨] ERD에 컬럼이 없어서 에러 유발
            hash_value=data["hash_value"]
        )
        self.db.add(new_version)
        
        history = RegulationChangeHistory(
            version=new_version,
            change_type="NE",
            change_summary=f"수집됨 ({category})"
        )
        self.db.add(history)
        
        await self.db.commit()
        print(f"✨ [DB 등록] {new_reg.title[:20]}... (S3 Uploaded)")
        return "created"

    async def _handle_existing_regulation(self, regulation: Regulation, data: dict, crawler: UniversalFetcher):
        category = data.get("category", "regulation")
        
        stmt = select(RegulationVersion).where(RegulationVersion.regulation_id == regulation.regulation_id).order_by(desc(RegulationVersion.version_number)).limit(1)
        result = await self.db.execute(stmt)
        latest_version = result.scalar_one_or_none()

        if latest_version and latest_version.hash_value == data["hash_value"]:
            return "skipped"

        # 파일 다시 다운로드 및 업로드
        storage_path = await self._upload_and_get_path(data["url"], data["hash_value"], crawler, category)
        
        new_v_num = latest_version.version_number + 1
        new_version = RegulationVersion(
            regulation_id=regulation.regulation_id,
            version_number=new_v_num,
            original_uri=data["url"],
            # file_path=storage_path, <-- [삭제됨]
            hash_value=data["hash_value"]
        )
        self.db.add(new_version)
        
        history = RegulationChangeHistory(
            version=new_version,
            change_type="A",
            change_summary=f"업데이트됨 ({category})"
        )
        self.db.add(history)
        
        await self.db.commit()
        print(f"🔄 [업데이트] v{new_v_num} (S3 Uploaded)")
        return "updated"

    # (_handle_existing_regulation 메서드도 동일하게 _upload_and_get_path 사용하도록 수정 필요)

    # ... (_handle_existing_regulation 도 동일하게 storage_path 사용하도록 수정) ...
