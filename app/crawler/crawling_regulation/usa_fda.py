import re
from bs4 import BeautifulSoup
from app.crawler.crawling_regulation.base import BaseCrawler
from typing import List, Dict, Any
from datetime import datetime
from dateutil import parser

class USAFDACrawler(BaseCrawler):
    # FDA 규제 목록 페이지
    TARGET_URL = "https://www.fda.gov/tobacco-products/rules-regulations-and-guidance/rules-and-regulations"

    async def run(self) -> List[Dict[str, Any]]:
        print(f"🇺🇸 [US] FDA 크롤링 시작: {self.TARGET_URL}")
        
        html = await self.fetch(self.TARGET_URL)
        if not html:
            return []

        results = await self.parse(html, self.TARGET_URL)
        return results

    async def parse(self, html: str, url: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        rows = soup.select("table tbody tr")
        if not rows:
            rows = soup.select(".views-row")

        if not rows:
            print("⚠️ 데이터를 찾을 수 없습니다. HTML 구조를 확인하세요.")
            return []

        for row in rows:
            try:
                # 1. 제목 및 링크 추출
                link_tag = row.select_one("a")
                if not link_tag:
                    continue
                
                title = link_tag.get_text(strip=True)
                href = link_tag.get("href")
                
                if href.startswith("/"):
                    full_url = f"https://www.fda.gov{href}"
                else:
                    full_url = href

                # 2. 날짜 추출 로직 (개선됨)
                date_str = None

                # [전략 1] URL에서 날짜 추출 (가장 정확함)
                # 패턴: .../documents/YYYY/MM/DD/...
                url_date_match = re.search(r'/documents/(\d{4})/(\d{2})/(\d{2})/', full_url)
                if url_date_match:
                    y, m, d = url_date_match.groups()
                    date_str = f"{y}-{m}-{d}"
                
                # [전략 2] HTML 텍스트에서 날짜 추출 (URL에 없을 경우)
                if not date_str:
                    row_text = row.get_text(" ", strip=True)
                    # 정규식: MM/DD/YYYY 또는 Month DD, YYYY
                    text_date_match = re.search(r'(\d{2}/\d{2}/\d{4})|([A-Z][a-z]+ \d{1,2}, \d{4})', row_text)
                    if text_date_match:
                        try:
                            dt = parser.parse(text_date_match.group(0))
                            date_str = dt.strftime("%Y-%m-%d")
                        except:
                            pass

                # [전략 3] Fallback (오늘 날짜)
                if not date_str:
                    # 날짜를 못 찾았다는 것을 알리기 위해 로그 출력 (디버깅용)
                    # print(f"⚠️ 날짜 추출 실패 (오늘 날짜 사용): {title[:30]}...") 
                    date_str = datetime.now().strftime("%Y-%m-%d")

                # 3. 해시 생성
                unique_content = f"{title}{full_url}"
                content_hash = self.generate_hash(unique_content)

                data = {
                    "country_code": "US",
                    "title": title,
                    "url": full_url,
                    "proclaimed_date": date_str,
                    "hash_value": content_hash,
                    "source_type": "html"
                }
                results.append(data)

            except Exception as e:
                print(f"⚠️ Parse Error: {e}")
                continue

        print(f"✅ [US] {len(results)}건의 규제 데이터 추출 완료")
        return results


