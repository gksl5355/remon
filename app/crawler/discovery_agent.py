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

