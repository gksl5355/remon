import time
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from datetime import datetime
from dateutil import parser

# Selenium 관련 임포트
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# BaseCrawler 상속 (hash 생성 등 유틸리티 사용을 위해)
from app.crawler.crawling_regulation.base import BaseCrawler

class SFBOSSeleniumCrawler(BaseCrawler):
    TARGET_URL = "https://sfbos.org/all-pages-docs?as_q=cigarette&cof=FORID%3A11&ie=UTF-8"

    def __init__(self):
        super().__init__()
        # 1. 크롬 옵션 설정 (WSL/서버 환경 최적화)
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # 화면 없이 실행
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")

        # 2. 드라이버 설정
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

    async def run(self) -> List[Dict[str, Any]]:
        print(f"🇺🇸 [SF] San Francisco BOS (Selenium) 시작: {self.TARGET_URL}")
        
        try:
            # 3. 페이지 접속
            self.driver.get(self.TARGET_URL)
            
            # 4. 자바스크립트 로딩 대기 (검색 결과가 나올 때까지 최대 10초 대기)
            # 구글 커스텀 검색 결과는 보통 'gsc-webResult' 클래스를 가집니다.
            print("⏳ JS 렌더링 대기 중...")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".gsc-webResult"))
            )
            
            # 5. 로딩된 HTML 가져오기
            html = self.driver.page_source
            
            # 6. 파싱 시작
            return self.parse(html, self.TARGET_URL)
            
        except Exception as e:
            print(f"❌ Selenium Error: {e}")
            return []
        finally:
            self.driver.quit()

    def parse(self, html: str, url: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Google Custom Search 결과 선택자
        rows = soup.select(".gsc-webResult.gsc-result")

        if not rows:
            print("⚠️ 데이터를 찾을 수 없습니다.")
            return []

        for row in rows:
            try:
                # A. 제목 및 링크
                link_tag = row.select_one("a.gs-title")
                if not link_tag:
                    continue
                
                # 구글 검색 결과는 텍스트가 깨질 수 있으므로 정제 필요
                title = link_tag.get_text(strip=True)
                href = link_tag.get("href") # data-ctorig 속성에 진짜 URL이 있을 수도 있음
                if link_tag.get("data-ctorig"):
                    href = link_tag.get("data-ctorig")

                if not href:
                    continue

                # B. 날짜 추출 (Snippet에서 찾기)
                snippet_div = row.select_one(".gs-snippet")
                snippet_text = snippet_div.get_text(strip=True) if snippet_div else ""
                
                date_str = datetime.now().strftime("%Y-%m-%d") # 기본값
                
                # 스니펫 앞부분에 날짜가 있는 경우가 많음 (예: "Sep 24, 2024 ...")
                # 정규식으로 날짜 찾기
                import re
                date_match = re.search(r'([A-Z][a-z]{2}\s\d{1,2},\s\d{4})', snippet_text)
                if date_match:
                    try:
                        dt = parser.parse(date_match.group(0))
                        date_str = dt.strftime("%Y-%m-%d")
                    except:
                        pass

                # C. 해시 생성
                unique_content = f"{title}{href}"
                content_hash = self.generate_hash(unique_content)

                data = {
                    "country_code": "US",
                    "title": title,
                    "url": href,
                    "proclaimed_date": date_str,
                    "hash_value": content_hash,
                    "source_type": "html" # or pdf check
                }
                results.append(data)

            except Exception as e:
                print(f"⚠️ Parse Error: {e}")
                continue
        
        print(f"✅ [SF] {len(results)}건 추출 완료")
        return results