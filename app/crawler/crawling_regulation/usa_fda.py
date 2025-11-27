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


# import re
# from bs4 import BeautifulSoup
# from app.crawler.base import BaseCrawler
# from typing import List, Dict, Any
# from datetime import datetime
# from dateutil import parser  # 날짜 파싱 라이브러리

# class USAFDACrawler(BaseCrawler):
#     # FDA 규제 목록 페이지
#     TARGET_URL = "https://www.fda.gov/tobacco-products/rules-regulations-and-guidance/rules-and-regulations"

#     async def run(self) -> List[Dict[str, Any]]:
#         print(f"🇺🇸 [US] FDA 크롤링 시작: {self.TARGET_URL}")
        
#         html = await self.fetch(self.TARGET_URL)
#         if not html:
#             return []

#         results = await self.parse(html, self.TARGET_URL)
#         return results

#     async def parse(self, html: str, url: str) -> List[Dict[str, Any]]:
#         soup = BeautifulSoup(html, "lxml")
#         results = []

#         # FDA 페이지는 보통 테이블(table) 안에 규제 목록이 있습니다.
#         rows = soup.select("table tbody tr")
        
#         # 테이블이 없으면 리스트 형태(.views-row)일 수도 있음
#         if not rows:
#             rows = soup.select(".views-row")

#         if not rows:
#             print("⚠️ 데이터를 찾을 수 없습니다. HTML 구조를 확인하세요.")
#             return []

#         for row in rows:
#             try:
#                 # 1. 제목 및 링크 추출
#                 link_tag = row.select_one("a")
#                 if not link_tag:
#                     continue
                
#                 title = link_tag.get_text(strip=True)
#                 href = link_tag.get("href")
                
#                 if href.startswith("/"):
#                     full_url = f"https://www.fda.gov{href}"
#                 else:
#                     full_url = href

#                 # 2. 날짜 추출 (Date Extraction) - 여기가 핵심 개선 포인트
#                 date_str = None
                
#                 # 전략 A: <time> 태그 찾기
#                 time_tag = row.select_one("time")
#                 if time_tag and time_tag.get("datetime"):
#                     date_str = time_tag.get("datetime")
                
#                 # 전략 B: 테이블 컬럼(td) 텍스트에서 날짜 형식 찾기
#                 if not date_str:
#                     # 모든 텍스트를 가져와서 날짜 패턴 검색 (예: 01/23/2024 or Jan 23, 2024)
#                     row_text = row.get_text(" ", strip=True)
#                     # 정규식: 월/일/년 또는 영문월 일, 년
#                     date_match = re.search(r'(\d{2}/\d{2}/\d{4})|([A-Z][a-z]+ \d{1,2}, \d{4})', row_text)
                    
#                     if date_match:
#                         raw_date = date_match.group(0)
#                         try:
#                             # "November 26, 2025" -> "2025-11-26" 변환
#                             dt = parser.parse(raw_date)
#                             date_str = dt.strftime("%Y-%m-%d")
#                         except:
#                             pass

#                 # 전략 C: 그래도 없으면 오늘 날짜 (Fallback)
#                 if not date_str:
#                     date_str = datetime.now().strftime("%Y-%m-%d")

#                 # 3. 해시 생성
#                 unique_content = f"{title}{full_url}"
#                 content_hash = self.generate_hash(unique_content)

#                 data = {
#                     "country_code": "US",
#                     "title": title,
#                     "url": full_url,
#                     "proclaimed_date": date_str,  # 추출한 실제 날짜
#                     "hash_value": content_hash,
#                     "source_type": "html"
#                 }
#                 results.append(data)

#             except Exception as e:
#                 print(f"⚠️ Parse Error: {e}")
#                 continue

#         print(f"✅ [US] {len(results)}건의 규제 데이터 추출 완료")
#         return results

# # app/crawler/usa_fda.py

# from bs4 import BeautifulSoup
# from app.crawler.base import BaseCrawler
# from typing import List, Dict, Any
# from datetime import datetime

# class USAFDACrawler(BaseCrawler):
#     TARGET_URL = "https://www.fda.gov/tobacco-products/rules-regulations-and-guidance/rules-and-regulations"

#     async def run(self) -> List[Dict[str, Any]]:
#         print(f"🇺🇸 [US] FDA 크롤링 시작: {self.TARGET_URL}")
        
#         html = await self.fetch(self.TARGET_URL)
#         if not html:
#             return []

#         results = await self.parse(html, self.TARGET_URL)
#         return results

#     async def parse(self, html: str, url: str) -> List[Dict[str, Any]]:
#         soup = BeautifulSoup(html, "lxml")
#         results = []

#         # [수정] 선택자 전략 변경
#         # 전략 1: 테이블 구조 (tbody > tr) 확인
#         rows = soup.select("table tbody tr")
        
#         # 전략 2: 테이블이 없으면 리스트 구조 (.views-row) 확인
#         if not rows:
#             rows = soup.select(".views-row")

#         # 디버깅: 여전히 못 찾으면 HTML 일부 출력
#         if not rows:
#             print("⚠️ 데이터를 찾을 수 없습니다. HTML 구조가 변경되었을 수 있습니다.")
#             # body 태그 내부의 처음 500자만 출력해서 확인
#             body = soup.find("body")
#             print(f"🔍 HTML Preview: {body.get_text()[:200] if body else 'No Body'}")
#             return []

#         for row in rows:
#             try:
#                 # 1. 링크(a 태그) 찾기
#                 link_tag = row.select_one("a")
#                 if not link_tag:
#                     continue
                
#                 title = link_tag.get_text(strip=True)
#                 href = link_tag.get("href")
                
#                 # 링크 정제
#                 if href.startswith("/"):
#                     full_url = f"https://www.fda.gov{href}"
#                 else:
#                     full_url = href

#                 # 2. 날짜 찾기 (time 태그 또는 테이블의 특정 열)
#                 # 테이블 구조일 경우 보통 날짜 열이 따로 있음 (여기서는 단순화)
#                 date_tag = row.select_one("time")
#                 if date_tag:
#                     date_str = date_tag.get("datetime")
#                 else:
#                     # 날짜 태그가 없으면 오늘 날짜 임시 사용 (추후 정밀 파싱 필요)
#                     date_str = datetime.now().strftime("%Y-%m-%d")

#                 # 3. 해시 생성
#                 unique_content = f"{title}{full_url}"
#                 content_hash = self.generate_hash(unique_content)

#                 data = {
#                     "country_code": "US",
#                     "title": title,
#                     "url": full_url,
#                     "proclaimed_date": date_str,
#                     "hash_value": content_hash,
#                     "source_type": "html"
#                 }
#                 results.append(data)

#             except Exception as e:
#                 print(f"⚠️ Parse Error: {e}")
#                 continue

#         print(f"✅ [US] {len(results)}건의 규제 데이터 추출 완료")
#         return results

