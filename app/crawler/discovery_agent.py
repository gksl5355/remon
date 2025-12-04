import asyncio
from typing import List, Dict
from tavily import TavilyClient
from app.core.repositories.crawl_repository import CrawlRepository
from app.crawler.crawling_regulation.base import UniversalFetcher

class DiscoveryAgent:
    def __init__(self, db_session, tavily_api_key: str):
        self.repository = CrawlRepository(db_session)
        self.tavily_client = None
        if tavily_api_key:
            self.tavily_client = TavilyClient(api_key=tavily_api_key)

    async def search_tavily(self, query: str) -> List[Dict]:
        if not self.tavily_client:
            return [] # Mock data 생략

        print(f"🔎 [Tavily] 탐색 중: '{query}'")
        try:
            response = await asyncio.to_thread(
                self.tavily_client.search,
                query=query,
                search_depth="basic",
                include_answer=False,
                include_raw_content=False,
                max_results=10  # [수정] 5개 -> 10개로 증가 (더 많은 결과)
            )
            return response.get('results', [])
        except Exception as e:
            print(f"❌ Tavily API 오류: {e}")
            return []

    async def run(self, country: str, keywords: List[str], category: str = "regulation"):
        """
        [수정] category 인자 추가 (regulation 또는 news)
        """
        # "news" 카테고리면 PDF 한정 검색을 풀어서 뉴스 기사도 나오게 함
        if category == "news":
            query = f"{country} {' '.join(keywords)}"
        else:
            # 규제는 PDF 위주로 검색
            query = f"{country} {' '.join(keywords)} filetype:pdf"
        
        results = await self.search_tavily(query)
        
        if not results:
            print(f"   💨 결과 없음")
            return

        print(f"   ✨ {len(results)}건 발견 ({category})")
        crawler = UniversalFetcher()
        
        try:
            for item in results:
                data = {
                    "url": item.get('url'),
                    "hash_value": crawler.generate_hash(item.get('url')),
                    "country_code": self._map_country_code(country),
                    "title": item.get('title'),
                    "proclaimed_date": None,
                    "source_id": 99,
                    "category": category  # [중요] 카테고리 전달
                }
                
                await self.repository.process_crawled_data(data, crawler)
                
        finally:
            await crawler.close()

    def _map_country_code(self, country_name: str) -> str:
        # 매핑 로직 (미국 연방, 캘리포니아 등을 US로 통일할지, 나눌지 결정)
        if "USA" in country_name: return "US"
        if "Russia" in country_name: return "RU"
        if "Indonesia" in country_name: return "ID"
        return "ZZ"

# import asyncio
# from typing import List, Dict
# from tavily import TavilyClient

# # 기존 모듈 임포트 유지
# from app.core.repositories.crawl_repository import CrawlRepository
# from app.crawler.crawling_regulation.base import UniversalFetcher

# class DiscoveryAgent:
#     """
#     [Tavily 기반 범용 규제 탐지 에이전트]
#     Google Search API 대신 Tavily를 사용하여
#     검색 + 본문 추출 + 노이즈 제거를 한 번에 수행합니다.
#     """
#     def __init__(self, db_session, tavily_api_key: str):
#         self.repository = CrawlRepository(db_session)
#         self.tavily_client = None
        
#         if tavily_api_key:
#             self.tavily_client = TavilyClient(api_key=tavily_api_key)
#         else:
#             print("⚠️ Tavily API Key가 없습니다. (Mock 모드)")

#     async def search_tavily(self, query: str) -> List[Dict]:
#         """
#         Tavily API를 사용하여 '고품질' 검색 결과 반환
#         """
#         if not self.tavily_client:
#             # Mock 데이터 (테스트용)
#             return [{
#                 "url": "https://eec.eaeunion.org/upload/medialibrary/1ad/TR-TS-035-2014.pdf",
#                 "content": "Technical regulation on tobacco products TR CU 035/2014 full text...",
#                 "title": "[Mock] Russia Tobacco Regulation PDF"
#             }]

#         print(f"🔎 [Tavily] 규제 탐색 중: '{query}'")
        
#         # Tavily의 강력한 기능: search_depth="advanced"를 쓰면 더 깊게 찾지만 크레딧 2배 소모
#         # 무료 티어 아끼기 위해 "basic" 사용 권장
#         try:
#             # 비동기 실행을 위해 to_thread 사용 (Tavily SDK는 기본적으로 동기)
#             response = await asyncio.to_thread(
#                 self.tavily_client.search,
#                 query=query,
#                 search_depth="basic", # advanced는 크레딧 소모 큼. basic 추천.
#                 include_answer=False, # 답변 생성 불필요 (토큰 절약)
#                 include_raw_content=False,
#                 max_results=5 # 상위 5개만 확인 (절약)
#             )
#             return response.get('results', [])
#         except Exception as e:
#             print(f"❌ Tavily API 오류: {e}")
#             return []

#     async def run(self, country: str, keywords: List[str]):
#         """
#         [실행 로직]
#         1. Tavily로 검색하여 [제목, URL, 본문요약]을 받아옴
#         2. PDF 파일이거나, 제목에 'Regulation'이 포함된 중요 링크만 선별
#         3. CrawlRepository로 다운로드 (PDF는 파일로, 웹은 텍스트로)
#         """
#         # 검색어 최적화: "filetype:pdf"를 붙이면 Tavily가 PDF를 잘 찾아줌
#         query = f"{country} {' '.join(keywords)} filetype:pdf"
        
#         # 1. Tavily 검색
#         results = await self.search_tavily(query)
        
#         if not results:
#             print(f"   💨 검색 결과가 없습니다.")
#             return

#         print(f"   ✨ Tavily가 {len(results)}개의 후보를 찾았습니다.")

#         # 2. 다운로드 및 저장
#         crawler = UniversalFetcher()
#         try:
#             for item in results:
#                 url = item.get('url')
#                 title = item.get('title')
#                 content = item.get('content') # Tavily가 긁어온 본문 일부

#                 # [필터링] Tavily는 이미 관련성 높은걸 주지만, 한 번 더 체크
#                 # 만약 content 내용이 너무 짧거나 광고 같으면 skip 하는 로직 추가 가능
                
#                 print(f"   📥 수집 시도: {title}")

#                 data = {
#                     "url": url,
#                     "hash_value": crawler.generate_hash(url),
#                     "country_code": self._map_country_code(country),
#                     "title": title,
#                     "proclaimed_date": None, # 메타데이터
#                     "source_id": 99, # Global Discovery Source
#                     "summary_preview": content # (옵션) Tavily가 준 요약을 저장하고 싶다면
#                 }

#                 # Repository가 URL에 접속해서 실제 파일(PDF)을 다운로드함
#                 await self.repository.process_crawled_data(data, crawler)
                
#         finally:
#             await crawler.close()

#     def _map_country_code(self, country_name: str) -> str:
#         mapping = {
#             "Russia": "RU", "Indonesia": "ID", "USA": "US", "Vietnam": "VN", "Korea": "KR"
#         }
#         return mapping.get(country_name, "ZZ")
