import re
import os
from bs4 import BeautifulSoup
from app.crawler.crawling_regulation.base import BaseCrawler
from typing import List, Dict, Any
from datetime import datetime

class CaliforniaLawCrawler(BaseCrawler):
    # [캘리포니아 민법(Civil Code) 예시 URL]
    TARGET_URL = "https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?lawCode=CIV&division=1.&title=&part=2.&chapter=&article=" 

    async def run(self) -> List[Dict[str, Any]]:
        print(f"🇺🇸 [CA] California Law 크롤링 시작: {self.TARGET_URL}")
        
        html = await self.fetch(self.TARGET_URL)
        if not html:
            return []

        results = await self.parse(html, self.TARGET_URL)
        return results

    async def parse(self, html: str, url: str) -> List[Dict[str, Any]]:
        # [수정 1] Warning 해결: "html.parser"를 명시적으로 사용
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # [수정 2] 실제 사이트 구조에 맞는 선택자 시도
        # 이 사이트는 보통 id="main_content" 또는 별도 ID 없이 <body> 안에 바로 내용이 있을 수 있음
        # 여러 후보군을 순서대로 찾아봅니다.
        container = soup.select_one("#main_content") or \
                    soup.select_one("#siteContent") or \
                    soup.select_one("form#myForm") or \
                    soup.select_one("body")
        
        if not container:
            print("⚠️ 콘텐츠 컨테이너를 찾을 수 없습니다.")
            # [디버깅] 무엇을 가져왔는지 파일로 저장해서 확인
            with open("california_debug.html", "w", encoding="utf-8") as f:
                f.write(soup.prettify())
            print("🐛 [Debug] 'california_debug.html' 파일을 생성했습니다. 열어서 구조를 확인해보세요.")
            return []

        # [수정 3] 링크 추출 로직 개선
        # 본문 내의 모든 링크(a)를 찾되, javascript: 같은 건 제외
        links = container.select("a") 
        print(f"🔎 발견된 링크 수: {len(links)}개")

        for link in links:
            try:
                title = link.get_text(strip=True)
                href = link.get("href")
                
                # 유효한 링크만 필터링
                if not href or "javascript" in href or href == "#":
                    continue
                
                # 제목이 너무 짧거나(페이지 이동 버튼 등) 비어있으면 패스
                if len(title) < 5:
                    continue

                # 상대 경로 -> 절대 경로 변환
                if not href.startswith("http"):
                    # 사이트 주소 구조에 맞게 조합
                    full_url = f"https://leginfo.legislature.ca.gov/faces/{href}"
                else:
                    full_url = href

                date_str = datetime.now().strftime("%Y-%m-%d")
                
                # 해시 생성
                unique_content = f"{title}{full_url}"
                content_hash = self.generate_hash(unique_content)

                data = {
                    "country_code": "US", # 일단 US로 통일 (DB FK 제약 때문)
                    "title": title,
                    "url": full_url,
                    "proclaimed_date": date_str,
                    "hash_value": content_hash,
                    "source_type": "html"
                }
                results.append(data)

            except Exception as e:
                # print(f"⚠️ Parse Error: {e}")
                continue
        
        print(f"✅ [CA] {len(results)}건 데이터 추출 완료")
        return results