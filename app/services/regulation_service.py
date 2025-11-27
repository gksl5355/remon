"""
module: regulation_service.py
description: 규제 문서 조회 및 크롤링 데이터 처리 비즈니스 로직
author: 조영우
created: 2025-11-12
updated: 2025-11-27
dependencies:
    - sqlalchemy.ext.asyncio
    - aiofiles
    - bs4
    - core.repositories.regulation_repository
    - core.models.regulation_model
"""

import os
import aiofiles
from bs4 import BeautifulSoup
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.repositories.regulation_keynote_repository import RegulationKeynoteRepository

# logger = logging.getLogger(__name__)
from sqlalchemy import select, desc

from app.config.logger import logger
from app.core.repositories.regulation_keynote_repository import RegulationKeynoteRepository
from app.core.models.regulation_model import Regulation, RegulationVersion, RegulationChangeHistory
from app.ai_pipeline.preprocess.preprocess_agent import PreprocessAgent

class RegulationService:
    """규제 문서 관련 비즈니스 로직(조회 및 크롤링 처리)을 처리하는 서비스 클래스"""

    def __init__(self, db: AsyncSession = None):
        """
        Args:
            db (AsyncSession, optional): 크롤링 로직에서 사용되는 DB 세션. 
                                         단순 조회(get_regulations) 시에는 필요하지 않을 수 있음.
        """
        # [기존] 조회용 리포지토리
        self.repo = RegulationKeynoteRepository()

        # [추가] 크롤링 및 전처리용 설정
        self.db = db
        self.preprocess_agent = PreprocessAgent()
        self.save_dir = os.path.join("db", "regulation")
        os.makedirs(self.save_dir, exist_ok=True)

    # ==========================================
    # [기존 기능] 규제 문서 조회 로직
    # ==========================================
    async def get_regulations(self, db: AsyncSession) -> dict:
        """
        규제 문서 목록을 조회한다.

        Args:
            db (AsyncSession): 데이터베이스 세션.

        Returns:
            dict: 규제 문서 목록 (프론트 형식).
        """
        
        # risk_level 한글 변환 맵
        RISK_LEVEL_MAP = {
            "Low": "낮음",
            "Medium": "보통",
            "High": "높음"
        }
        
        try:
            # keynote와 impact_score를 포함하여 조회
            regulations = await self.repo.get_all_keynotes(db)
            result = []
            for keynote in regulations:
                # keynote_text는 ["country: US", "category: demo", ...] 형태
                keynote_data = {}
                for item in keynote.keynote_text:
                    if ": " in item:
                        key, value = item.split(": ", 1)
                        keynote_data[key] = value
                
                # 프론트 형식으로 변환
                result.append({
                    "id": keynote.keynote_id,
                    "country": keynote_data.get("country", ""),
                    "category": keynote_data.get("category", ""),
                    "summary": keynote_data.get("summary", ""),
                    "impact": RISK_LEVEL_MAP.get(keynote_data.get("impact", ""), keynote_data.get("impact", ""))
                })
            
            logger.info(f"Found {len(result)} regulations")
            return {
                "today_count": len(result),
                "regulations": result #db에서 가져온 json 구조?
            }
            
        except Exception as e:
            logger.error(f"Error fetching regulations: {e}", exc_info=True)
            # 에러 발생해도 빈 배열 반환
            return {
                "today_count": 0,
                "regulations": []
            }

    # ==========================================
    # [추가 기능] 크롤링 데이터 처리 로직
    # ==========================================
    async def process_crawled_data(self, data: dict, crawler=None):
        if not self.db:
            logger.error("DB session is not initialized for crawling process.")
            return "error: no_db_session"

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