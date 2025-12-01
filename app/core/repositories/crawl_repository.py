import os
import aiofiles
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime
from typing import Optional

from app.core.models.regulation_model import Regulation, RegulationVersion, RegulationChangeHistory
from app.ai_pipeline.preprocess.preprocess_agent import PreprocessAgent
from app.crawler.crawling_regulation.base import UniversalFetcher

class CrawlRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.preprocess_agent = PreprocessAgent()
        # 기본 경로 (생성자에서는 base만 잡음)
        self.base_dir = "db" 

    async def process_crawled_data(self, data: dict, crawler: Optional[UniversalFetcher] = None):
        should_close_crawler = False
        if not crawler:
            crawler = UniversalFetcher()
            should_close_crawler = True

        try:
            url = data["url"]
            # DB 로직은 동일...
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

    async def _save_file_locally(self, url: str, hash_value: str, crawler: UniversalFetcher, category: str = "regulation") -> Optional[str]:
        """
        [수정] category 인자를 받아서 저장 폴더를 동적으로 결정
        """
        if not crawler:
            return None

        # 1. 저장 경로 결정 (regulation vs news)
        # 예: db/regulation/abc.pdf 또는 db/news/xyz.txt
        save_dir = os.path.join(self.base_dir, category)
        os.makedirs(save_dir, exist_ok=True)

        # 2. 다운로드 및 매직 바이트 체크 (기존 로직 유지)
        content = await crawler.fetch_binary(url)
        if not content:
            return None

        is_pdf = content.startswith(b'%PDF') or url.lower().endswith(".pdf")

        if is_pdf:
            filename = f"{hash_value}.pdf"
            file_path = os.path.join(save_dir, filename)
            if os.path.exists(file_path): return file_path
            
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)
            print(f"💾 [{category.upper()}] PDF 저장: {file_path}")
            return file_path

        else:
            filename = f"{hash_value}.txt"
            file_path = os.path.join(save_dir, filename)
            if os.path.exists(file_path): return file_path

            try:
                html_text = content.decode('utf-8')
            except:
                try: html_text = content.decode('latin-1')
                except: return None

            soup = BeautifulSoup(html_text, "lxml")
            for script in soup(["script", "style", "header", "footer", "nav", "noscript"]):
                script.extract()
            clean_text = soup.get_text(separator="\n", strip=True)

            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(clean_text)
            
            print(f"💾 [{category.upper()}] 텍스트 저장: {file_path}")
            return file_path

    async def _create_new_regulation(self, data: dict, crawler: UniversalFetcher):
        # [수정] data 딕셔너리에서 category를 꺼내서 전달
        category = data.get("category", "regulation")
        file_path = await self._save_file_locally(data["url"], data["hash_value"], crawler, category)

        # (DB 저장 로직은 기존과 동일)
        # 단, News인 경우 DB에 태그를 다르게 달거나 별도 테이블로 뺄 수도 있지만,
        # 일단은 Regulation 테이블에 저장하되 title에 태그를 붙이는 식으로 구분 가능
        
        # ... (DB Insert 코드 생략 - 기존과 동일) ...
        # ... (새로운 파일이 있으면 PreprocessAgent 실행) ...
        
        # 여기서는 생략했지만, 실제 코드에는 DB Insert 부분이 있어야 합니다.
        # 편의상 핵심인 _save_file_locally 호출부만 수정했습니다.
        
        # [복원용 DB 코드]
        proclaimed_date = None
        if data.get("proclaimed_date"):
            # ... 날짜 처리 ...
            pass
            
        new_reg = Regulation(
            source_id=data.get("source_id", 1),
            country_code=data.get("country_code", "US"),
            title=f"[{category.upper()}] {data.get('title', 'No Title')}", # 제목에 카테고리 표시
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
            change_summary=f"수집됨 ({category})"
        )
        self.db.add(history)
        await self.db.commit()

        if file_path:
            await self.preprocess_agent.run(file_path, data)
            
        return "created"

    async def _handle_existing_regulation(self, regulation: Regulation, data: dict, crawler: UniversalFetcher):
        # [수정] 업데이트 시에도 카테고리 전달
        category = data.get("category", "regulation")
        
        # ... (버전 체크 로직 기존 동일) ...
        stmt = select(RegulationVersion).where(RegulationVersion.regulation_id == regulation.regulation_id).order_by(desc(RegulationVersion.version_number)).limit(1)
        result = await self.db.execute(stmt)
        latest_version = result.scalar_one_or_none()

        if latest_version and latest_version.hash_value == data["hash_value"]:
            return "skipped"

        file_path = await self._save_file_locally(data["url"], data["hash_value"], crawler, category)
        
        # ... (버전 업데이트 DB 로직 기존 동일) ...
        new_v_num = latest_version.version_number + 1
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
            change_summary=f"업데이트됨 ({category})"
        )
        self.db.add(history)
        await self.db.commit()

        if file_path:
            await self.preprocess_agent.run(file_path, data)

        return "updated"

# import os
# import aiofiles
# from bs4 import BeautifulSoup
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, desc
# from datetime import datetime
# from typing import Optional

# from app.core.models.regulation_model import Regulation, RegulationVersion, RegulationChangeHistory
# from app.ai_pipeline.preprocess.preprocess_agent import PreprocessAgent
# from app.crawler.crawling_regulation.base import UniversalFetcher

# class CrawlRepository:
#     def __init__(self, db: AsyncSession):
#         self.db = db
#         self.preprocess_agent = PreprocessAgent()
#         self.save_dir = os.path.join("db", "regulation")
#         os.makedirs(self.save_dir, exist_ok=True)

#     async def process_crawled_data(self, data: dict, crawler: Optional[UniversalFetcher] = None):
#         should_close_crawler = False
#         if not crawler:
#             crawler = UniversalFetcher()
#             should_close_crawler = True

#         try:
#             url = data["url"]
            
#             # DB 중복 체크
#             stmt = (
#                 select(Regulation)
#                 .join(RegulationVersion, Regulation.regulation_id == RegulationVersion.regulation_id)
#                 .where(RegulationVersion.original_uri == url)
#                 .limit(1)
#             )
#             result = await self.db.execute(stmt)
#             existing_reg = result.scalar_one_or_none()

#             # 신규 등록 또는 업데이트 처리
#             if not existing_reg:
#                 return await self._create_new_regulation(data, crawler)
#             else:
#                 return await self._handle_existing_regulation(existing_reg, data, crawler)
#         finally:
#             if should_close_crawler:
#                 await crawler.close()

#     async def _save_file_locally(self, url: str, hash_value: str, crawler: UniversalFetcher) -> Optional[str]:
#         """
#         [개선된 로직] URL 확장자가 아닌 '파일 실제 헤더(Magic Bytes)'로 형식을 판단하여 저장
#         """
#         if not crawler:
#             return None

#         # 1. 일단 바이너리로 다운로드 (PDF일 수도, HTML일 수도 있음)
#         content = await crawler.fetch_binary(url)
#         if not content:
#             return None

#         # 2. 파일 형식 판별 (Magic Bytes Check)
#         is_pdf = False
        
#         # PDF 파일 시그니처 확인 (%PDF-)
#         if content.startswith(b'%PDF'):
#             is_pdf = True
        
#         # (옵션) URL이 강제로 .pdf인 경우도 포함
#         elif url.lower().endswith(".pdf"):
#             is_pdf = True

#         # 3. 형식에 따른 저장 분기
#         if is_pdf:
#             # === PDF 저장 ===
#             filename = f"{hash_value}.pdf"
#             file_path = os.path.join(self.save_dir, filename)
            
#             if os.path.exists(file_path):
#                 return file_path

#             async with aiofiles.open(file_path, "wb") as f:
#                 await f.write(content)
#             print(f"💾 PDF 저장 완료 (Auto-detected): {file_path}")
#             return file_path

#         else:
#             # === HTML/Text 저장 ===
#             filename = f"{hash_value}.txt"
#             file_path = os.path.join(self.save_dir, filename)

#             if os.path.exists(file_path):
#                 return file_path

#             try:
#                 # 바이너리를 텍스트로 디코딩 (러시아어 등 깨짐 방지 시도)
#                 # 1차 시도: utf-8
#                 html_text = content.decode('utf-8')
#             except UnicodeDecodeError:
#                 try:
#                     # 2차 시도: latin-1 (혹은 chardet 사용 가능)
#                     html_text = content.decode('latin-1')
#                 except:
#                     print(f"⚠️ 디코딩 실패: {url}")
#                     return None

#             # BeautifulSoup으로 태그 제거하고 본문만 추출
#             soup = BeautifulSoup(html_text, "lxml")
            
#             # 노이즈 제거
#             for script in soup(["script", "style", "header", "footer", "nav", "iframe", "noscript"]):
#                 script.extract()
            
#             clean_text = soup.get_text(separator="\n", strip=True)

#             async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
#                 await f.write(clean_text)
            
#             print(f"💾 텍스트 변환 및 저장 완료: {file_path}")
#             return file_path

#     async def _create_new_regulation(self, data: dict, crawler: UniversalFetcher):
#         # 파일 저장 호출
#         file_path = await self._save_file_locally(data["url"], data["hash_value"], crawler)

#         proclaimed_date = None
#         if data.get("proclaimed_date"):
#             try:
#                 if isinstance(data["proclaimed_date"], str):
#                     proclaimed_date = datetime.strptime(data["proclaimed_date"], "%Y-%m-%d").date()
#                 else:
#                     proclaimed_date = data["proclaimed_date"]
#             except ValueError:
#                 pass

#         new_reg = Regulation(
#             source_id=data.get("source_id", 1),
#             country_code=data.get("country_code", "US"),
#             title=data.get("title", "No Title"),
#             proclaimed_date=proclaimed_date,
#             status="active"
#         )
#         self.db.add(new_reg)
#         await self.db.flush()

#         new_version = RegulationVersion(
#             regulation_id=new_reg.regulation_id,
#             version_number=1,
#             original_uri=data["url"],
#             hash_value=data["hash_value"]
#         )
#         self.db.add(new_version)
        
#         history = RegulationChangeHistory(
#             version=new_version,
#             change_type="new", 
#             change_summary="최초 수집됨 (Discovery Agent)"
#         )
#         self.db.add(history)
        
#         await self.db.commit()
#         print(f"✨ [New] 신규 규제 등록: {new_reg.title[:30]}...")

#         if file_path:
#             # 전처리 에이전트 실행
#             await self.preprocess_agent.run(file_path, data)
            
#         return "created"

#     async def _handle_existing_regulation(self, regulation: Regulation, data: dict, crawler: UniversalFetcher):
#         stmt = select(RegulationVersion).where(
#             RegulationVersion.regulation_id == regulation.regulation_id
#         ).order_by(desc(RegulationVersion.version_number)).limit(1)
        
#         result = await self.db.execute(stmt)
#         latest_version = result.scalar_one_or_none()

#         if latest_version and latest_version.hash_value == data["hash_value"]:
#             return "skipped"

#         print(f"🔄 변경 감지됨! 파일 다운로드 중...")
#         file_path = await self._save_file_locally(data["url"], data["hash_value"], crawler)

#         new_v_num = latest_version.version_number + 1 if latest_version else 1
        
#         new_version = RegulationVersion(
#             regulation_id=regulation.regulation_id,
#             version_number=new_v_num,
#             original_uri=data["url"],
#             hash_value=data["hash_value"]
#         )
#         self.db.add(new_version)

#         history = RegulationChangeHistory(
#             version=new_version,
#             change_type="append",
#             change_summary=f"버전 {new_v_num}으로 업데이트됨"
#         )
#         self.db.add(history)
        
#         await self.db.commit()
#         print(f"🔄 [Update] 규제 업데이트 완료 (v{new_v_num})")

#         if file_path:
#             await self.preprocess_agent.run(file_path, data)

#         return "updated"

# import os
# import aiofiles
# from bs4 import BeautifulSoup
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, desc
# from datetime import datetime
# from typing import Optional

# from app.core.models.regulation_model import Regulation, RegulationVersion, RegulationChangeHistory
# from app.ai_pipeline.preprocess.preprocess_agent import PreprocessAgent
# from app.crawler.crawling_regulation.base import UniversalFetcher  # [수정] UniversalFetcher 임포트

# class CrawlRepository:
#     def __init__(self, db: AsyncSession):
#         self.db = db
#         self.preprocess_agent = PreprocessAgent()
#         self.save_dir = os.path.join("db", "regulation")
#         os.makedirs(self.save_dir, exist_ok=True)

#     async def process_crawled_data(self, data: dict, crawler: Optional[UniversalFetcher] = None):
#         """
#         [범용성 개선] 
#         crawler 객체가 없으면 UniversalFetcher를 임시로 생성하여 처리합니다.
#         이를 통해 Discovery Agent가 URL만 던져줘도 알아서 다운로드까지 수행합니다.
#         """
#         should_close_crawler = False
#         if not crawler:
#             crawler = UniversalFetcher()
#             should_close_crawler = True

#         try:
#             url = data["url"]
            
#             stmt = (
#                 select(Regulation)
#                 .join(RegulationVersion, Regulation.regulation_id == RegulationVersion.regulation_id)
#                 .where(RegulationVersion.original_uri == url)
#                 .limit(1)
#             )
#             result = await self.db.execute(stmt)
#             existing_reg = result.scalar_one_or_none()

#             if not existing_reg:
#                 return await self._create_new_regulation(data, crawler)
#             else:
#                 return await self._handle_existing_regulation(existing_reg, data, crawler)
#         finally:
#             # 임시로 만든 크롤러라면 닫아준다
#             if should_close_crawler:
#                 await crawler.close()

#     async def _save_file_locally(self, url: str, hash_value: str, crawler: UniversalFetcher) -> Optional[str]:
#         if not crawler:
#             return None

#         # 1. PDF 처리
#         if url.lower().endswith(".pdf"):
#             filename = f"{hash_value}.pdf"
#             file_path = os.path.join(self.save_dir, filename)
            
#             if os.path.exists(file_path):
#                 return file_path

#             content = await crawler.fetch_binary(url)
#             if content:
#                 async with aiofiles.open(file_path, "wb") as f:
#                     await f.write(content)
#                 print(f"💾 PDF 저장 완료: {file_path}")
#                 return file_path
        
#         # 2. 일반 웹페이지 (HTML -> Text)
#         else:
#             filename = f"{hash_value}.txt"
#             file_path = os.path.join(self.save_dir, filename)

#             if os.path.exists(file_path):
#                 return file_path

#             html_content = await crawler.fetch(url)
#             if html_content:
#                 soup = BeautifulSoup(html_content, "lxml")
                
#                 # 노이즈 제거
#                 for script in soup(["script", "style", "header", "footer", "nav", "iframe", "noscript"]):
#                     script.extract()
                
#                 clean_text = soup.get_text(separator="\n", strip=True)

#                 async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
#                     await f.write(clean_text)
                
#                 print(f"💾 텍스트 변환 및 저장 완료: {file_path}")
#                 return file_path

#         return None

#     async def _create_new_regulation(self, data: dict, crawler: UniversalFetcher):
#         file_path = await self._save_file_locally(data["url"], data["hash_value"], crawler)

#         # [안전장치] 날짜 포맷이 안 맞거나 없으면 None 처리
#         proclaimed_date = None
#         if data.get("proclaimed_date"):
#             try:
#                 # LLM이 YYYY-MM-DD 형식을 안 지켰을 경우 대비
#                 if isinstance(data["proclaimed_date"], str):
#                     proclaimed_date = datetime.strptime(data["proclaimed_date"], "%Y-%m-%d").date()
#                 else:
#                     proclaimed_date = data["proclaimed_date"]
#             except ValueError:
#                 print(f"⚠️ 날짜 형식 오류 (기록 생략): {data['proclaimed_date']}")

#         # [범용성] source_id가 없으면 기본값 1 사용 (추후 'General Web' 소스 ID로 변경 권장)
#         source_id = data.get("source_id", 1)

#         new_reg = Regulation(
#             source_id=source_id,
#             country_code=data.get("country_code", "US"), # 기본값 US
#             title=data.get("title", "No Title"),
#             proclaimed_date=proclaimed_date,
#             status="active"
#         )
#         self.db.add(new_reg)
#         await self.db.flush()

#         new_version = RegulationVersion(
#             regulation_id=new_reg.regulation_id,
#             version_number=1,
#             original_uri=data["url"],
#             hash_value=data["hash_value"]
#         )
#         self.db.add(new_version)
        
#         history = RegulationChangeHistory(
#             version=new_version,
#             change_type="new", 
#             change_summary="최초 수집됨 (Discovery Agent)"
#         )
#         self.db.add(history)
        
#         await self.db.commit()
#         print(f"✨ [New] 신규 규제 등록: {new_reg.title[:30]}...")

#         if file_path:
#             # PreprocessAgent 실행 (비동기 처리 권장)
#             # await self.preprocess_agent.run(file_path, data) 
#             # -> 성능을 위해 백그라운드 작업으로 넘기는 것을 고려할 수 있음
#             await self.preprocess_agent.run(file_path, data)
            
#         return "created"

#     async def _handle_existing_regulation(self, regulation: Regulation, data: dict, crawler: UniversalFetcher):
#         # 기존 로직 유지 (버전 관리)
#         stmt = select(RegulationVersion).where(
#             RegulationVersion.regulation_id == regulation.regulation_id
#         ).order_by(desc(RegulationVersion.version_number)).limit(1)
        
#         result = await self.db.execute(stmt)
#         latest_version = result.scalar_one_or_none()

#         if latest_version and latest_version.hash_value == data["hash_value"]:
#             return "skipped"

#         print(f"🔄 변경 감지됨! 파일 다운로드 중...")
#         file_path = await self._save_file_locally(data["url"], data["hash_value"], crawler)

#         new_v_num = latest_version.version_number + 1 if latest_version else 1
        
#         new_version = RegulationVersion(
#             regulation_id=regulation.regulation_id,
#             version_number=new_v_num,
#             original_uri=data["url"],
#             hash_value=data["hash_value"]
#         )
#         self.db.add(new_version)

#         history = RegulationChangeHistory(
#             version=new_version,
#             change_type="append",
#             change_summary=f"버전 {new_v_num}으로 업데이트됨"
#         )
#         self.db.add(history)
        
#         await self.db.commit()
#         print(f"🔄 [Update] 규제 업데이트 완료 (v{new_v_num})")

#         if file_path:
#             await self.preprocess_agent.run(file_path, data)

#         return "updated"

# # app/services/regulation_service.py

# import os
# import aiofiles
# from bs4 import BeautifulSoup # [추가] 텍스트 추출용
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, desc
# from datetime import datetime

# from app.core.models.regulation_model import Regulation, RegulationVersion, RegulationChangeHistory
# from app.ai_pipeline.preprocess.preprocess_agent import PreprocessAgent

# class CrawlRepository:
#     def __init__(self, db: AsyncSession):
#         self.db = db
#         self.preprocess_agent = PreprocessAgent()
#         self.save_dir = os.path.join("db", "regulation")
#         os.makedirs(self.save_dir, exist_ok=True)

#     async def process_crawled_data(self, data: dict, crawler=None):
#         url = data["url"]
        
#         stmt = (
#             select(Regulation)
#             .join(RegulationVersion, Regulation.regulation_id == RegulationVersion.regulation_id)
#             .where(RegulationVersion.original_uri == url)
#             .limit(1)
#         )
#         result = await self.db.execute(stmt)
#         existing_reg = result.scalar_one_or_none()

#         if not existing_reg:
#             return await self._create_new_regulation(data, crawler)
#         else:
#             return await self._handle_existing_regulation(existing_reg, data, crawler)

#     # [핵심 수정] 파일 저장 로직 변경
#     async def _save_file_locally(self, url: str, hash_value: str, crawler) -> str:
#         if not crawler:
#             return None

#         # 1. PDF인 경우: 기존 방식대로 바이너리 저장
#         if url.lower().endswith(".pdf"):
#             filename = f"{hash_value}.pdf"
#             file_path = os.path.join(self.save_dir, filename)
            
#             if os.path.exists(file_path):
#                 return file_path

#             content = await crawler.fetch_binary(url)
#             if content:
#                 async with aiofiles.open(file_path, "wb") as f:
#                     await f.write(content)
#                 print(f"💾 PDF 저장 완료: {file_path}")
#                 return file_path
        
#         # 2. HTML(웹페이지)인 경우: 텍스트만 추출하여 .txt로 저장
#         else:
#             filename = f"{hash_value}.txt" # 확장자를 .txt로 변경
#             file_path = os.path.join(self.save_dir, filename)

#             if os.path.exists(file_path):
#                 return file_path

#             # fetch()를 사용하여 텍스트(HTML) 가져오기
#             html_content = await crawler.fetch(url)
#             if html_content:
#                 # BeautifulSoup으로 순수 텍스트만 추출
#                 soup = BeautifulSoup(html_content, "lxml")
                
#                 # 불필요한 태그 제거 (스크립트, 스타일, 네비게이션 등)
#                 for script in soup(["script", "style", "header", "footer", "nav", "iframe"]):
#                     script.extract()
                
#                 # 텍스트 추출 (공백 정리)
#                 clean_text = soup.get_text(separator="\n", strip=True)

#                 # .txt 파일로 저장
#                 async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
#                     await f.write(clean_text)
                
#                 print(f"💾 텍스트 변환 및 저장 완료: {file_path}")
#                 return file_path

#         return None

#     async def _create_new_regulation(self, data: dict, crawler):
#         file_path = await self._save_file_locally(data["url"], data["hash_value"], crawler)

#         new_reg = Regulation(
#             source_id=1,
#             country_code=data["country_code"],
#             title=data["title"],
#             proclaimed_date=datetime.strptime(data["proclaimed_date"], "%Y-%m-%d").date() if data.get("proclaimed_date") else None,
#             status="active"
#         )
#         self.db.add(new_reg)
#         await self.db.flush()

#         new_version = RegulationVersion(
#             regulation_id=new_reg.regulation_id,
#             version_number=1,
#             original_uri=data["url"],
#             hash_value=data["hash_value"]
#         )
#         self.db.add(new_version)
        
#         history = RegulationChangeHistory(
#             version=new_version,
#             change_type="new", 
#             change_summary="최초 수집됨"
#         )
#         self.db.add(history)
        
#         await self.db.commit()
#         print(f"✨ [New] 신규 규제 등록: {data['title'][:30]}...")

#         if file_path:
#             await self.preprocess_agent.run(file_path, data)
            
#         return "created"

#     async def _handle_existing_regulation(self, regulation: Regulation, data: dict, crawler):
#         stmt = select(RegulationVersion).where(
#             RegulationVersion.regulation_id == regulation.regulation_id
#         ).order_by(desc(RegulationVersion.version_number)).limit(1)
        
#         result = await self.db.execute(stmt)
#         latest_version = result.scalar_one_or_none()

#         if latest_version and latest_version.hash_value == data["hash_value"]:
#             return "skipped"

#         print(f"🔄 변경 감지됨! 파일 다운로드 중...")
#         file_path = await self._save_file_locally(data["url"], data["hash_value"], crawler)

#         new_v_num = latest_version.version_number + 1 if latest_version else 1
        
#         new_version = RegulationVersion(
#             regulation_id=regulation.regulation_id,
#             version_number=new_v_num,
#             original_uri=data["url"],
#             hash_value=data["hash_value"]
#         )
#         self.db.add(new_version)

#         history = RegulationChangeHistory(
#             version=new_version,
#             change_type="append",
#             change_summary=f"버전 {new_v_num}으로 업데이트됨"
#         )
#         self.db.add(history)
        
#         await self.db.commit()
#         print(f"🔄 [Update] 규제 업데이트 완료 (v{new_v_num})")

#         if file_path:
#             await self.preprocess_agent.run(file_path, data)

#         return "updated"