import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from app.crawler.crawling_regulation.base import BaseCrawler
from typing import List, Dict, Any

class RussiaEECCrawler(BaseCrawler):
    # 유라시아 경제 연합(EAEU) 기술 규정 페이지 (담배)
    # 사용자가 제공한 URL이 404일 경우를 대비해 상위 목록 페이지도 고려해야 하지만, 
    # 일단 제공해주신 URL 패턴을 따르되, 실제 작동하는 목록 페이지를 타겟팅합니다.
    TARGET_URL = "https://eec.eaeunion.org/comission/department/deptexreg/tr/tabac.php"

    async def run(self) -> List[Dict[str, Any]]:
        print(f"🇷🇺 [RU] EAEU(Russia) 규제 크롤링 시작: {self.TARGET_URL}")
        
        html = await self.fetch(self.TARGET_URL)
        if not html:
            # 혹시 URL이 변경되었을 수 있으니 메인 기술규정 페이지도 백업으로 고려 가능
            print("❌ 페이지를 불러올 수 없습니다.")
            return []

        results = await self.parse(html, self.TARGET_URL)
        return results

    async def parse(self, html: str, url: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # EEC 사이트는 보통 규제 목록을 텍스트 링크로 제공합니다.
        # "035/2014" (담배 규제 번호)가 포함된 링크를 모두 찾습니다.
        # 러시아어: "ТР ТС 035/2014" (TR CU 035/2014)
        target_keyword = "035/2014"
        
        # 본문 영역 찾기 (사이트 구조에 따라 다를 수 있음, 일반적으로 content 영역)
        content_div = soup.select_one(".content") or soup.body

        links = content_div.find_all("a", href=True)

        for link in links:
            link_text = link.get_text(strip=True)
            href = link.get("href")

            # 링크 텍스트나 href에 규제 번호가 있는지 확인
            if target_keyword in link_text or target_keyword in href:
                
                # 정제된 제목
                title = link_text if len(link_text) > 10 else f"TR CU {target_keyword} Document"
                
                # 절대 경로 변환
                full_url = urljoin(url, href)

                # 파일 확장자 확인 (PDF나 DOCX인 경우가 많음)
                ext = "html"
                if full_url.lower().endswith(".pdf"):
                    ext = "pdf"
                elif full_url.lower().endswith(".doc") or full_url.lower().endswith(".docx"):
                    ext = "doc"

                # 날짜: 페이지에서 추출하기 어려우면 오늘 날짜 (이후 메타데이터 개선 가능)
                date_str = datetime.now().strftime("%Y-%m-%d")

                # 해시 생성
                unique_content = f"{title}{full_url}"
                content_hash = self.generate_hash(unique_content)

                data = {
                    "country_code": "RU", # 러시아/EAEU
                    "title": title,
                    "url": full_url,
                    "proclaimed_date": date_str,
                    "hash_value": content_hash,
                    "source_type": ext # pdf, doc, html 등
                }
                
                # 중복 링크 제거를 위해 리스트에 없는 경우만 추가
                if not any(d['url'] == full_url for d in results):
                    results.append(data)

        print(f"✅ [RU] {len(results)}건의 규제 문서 발견")
        return results