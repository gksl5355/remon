# app/services/regulation_service.py

import os
import aiofiles
from bs4 import BeautifulSoup # [추가] 텍스트 추출용
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime

from app.core.models.regulation_model import Regulation, RegulationVersion, RegulationChangeHistory
from app.ai_pipeline.preprocess.preprocess_agent import PreprocessAgent

class CrawlRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.preprocess_agent = PreprocessAgent()
        self.save_dir = os.path.join("db", "regulation")
        os.makedirs(self.save_dir, exist_ok=True)

    async def process_crawled_data(self, data: dict, crawler=None):
        url = data["url"]
        
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

    # [핵심 수정] 파일 저장 로직 변경
    async def _save_file_locally(self, url: str, hash_value: str, crawler) -> str:
        if not crawler:
            return None

        # 1. PDF인 경우: 기존 방식대로 바이너리 저장
        if url.lower().endswith(".pdf"):
            filename = f"{hash_value}.pdf"
            file_path = os.path.join(self.save_dir, filename)
            
            if os.path.exists(file_path):
                return file_path

            content = await crawler.fetch_binary(url)
            if content:
                async with aiofiles.open(file_path, "wb") as f:
                    await f.write(content)
                print(f"💾 PDF 저장 완료: {file_path}")
                return file_path
        
        # 2. HTML(웹페이지)인 경우: 텍스트만 추출하여 .txt로 저장
        else:
            filename = f"{hash_value}.txt" # 확장자를 .txt로 변경
            file_path = os.path.join(self.save_dir, filename)

            if os.path.exists(file_path):
                return file_path

            # fetch()를 사용하여 텍스트(HTML) 가져오기
            html_content = await crawler.fetch(url)
            if html_content:
                # BeautifulSoup으로 순수 텍스트만 추출
                soup = BeautifulSoup(html_content, "lxml")
                
                # 불필요한 태그 제거 (스크립트, 스타일, 네비게이션 등)
                for script in soup(["script", "style", "header", "footer", "nav", "iframe"]):
                    script.extract()
                
                # 텍스트 추출 (공백 정리)
                clean_text = soup.get_text(separator="\n", strip=True)

                # .txt 파일로 저장
                async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                    await f.write(clean_text)
                
                print(f"💾 텍스트 변환 및 저장 완료: {file_path}")
                return file_path

        return None

    async def _create_new_regulation(self, data: dict, crawler):
        file_path = await self._save_file_locally(data["url"], data["hash_value"], crawler)

        new_reg = Regulation(
            source_id=1,
            country_code=data["country_code"],
            title=data["title"],
            proclaimed_date=datetime.strptime(data["proclaimed_date"], "%Y-%m-%d").date() if data.get("proclaimed_date") else None,
            status="active"
        )
        self.db.add(new_reg)
        await self.db.flush()

        new_version = RegulationVersion(
            regulation_id=new_reg.regulation_id,
            version_number=1,
            original_uri=data["url"],
            hash_value=data["hash_value"]
        )
        self.db.add(new_version)
        
        history = RegulationChangeHistory(
            version=new_version,
            change_type="new", 
            change_summary="최초 수집됨"
        )
        self.db.add(history)
        
        await self.db.commit()
        print(f"✨ [New] 신규 규제 등록: {data['title'][:30]}...")

        if file_path:
            await self.preprocess_agent.run(file_path, data)
            
        return "created"

    async def _handle_existing_regulation(self, regulation: Regulation, data: dict, crawler):
        stmt = select(RegulationVersion).where(
            RegulationVersion.regulation_id == regulation.regulation_id
        ).order_by(desc(RegulationVersion.version_number)).limit(1)
        
        result = await self.db.execute(stmt)
        latest_version = result.scalar_one_or_none()

        if latest_version and latest_version.hash_value == data["hash_value"]:
            return "skipped"

        print(f"🔄 변경 감지됨! 파일 다운로드 중...")
        file_path = await self._save_file_locally(data["url"], data["hash_value"], crawler)

        new_v_num = latest_version.version_number + 1 if latest_version else 1
        
        new_version = RegulationVersion(
            regulation_id=regulation.regulation_id,
            version_number=new_v_num,
            original_uri=data["url"],
            hash_value=data["hash_value"]
        )
        self.db.add(new_version)

        history = RegulationChangeHistory(
            version=new_version,
            change_type="append",
            change_summary=f"버전 {new_v_num}으로 업데이트됨"
        )
        self.db.add(history)
        
        await self.db.commit()
        print(f"🔄 [Update] 규제 업데이트 완료 (v{new_v_num})")

        if file_path:
            await self.preprocess_agent.run(file_path, data)

        return "updated"