import httpx
from typing import List, Dict, Any
from datetime import datetime
from app.crawler.crawling_regulation.base import BaseCrawler

class ECFRAPICrawler(BaseCrawler):
    API_URL = "https://www.ecfr.gov/api/search/v1/results"

    def __init__(self, title_number: str = "21", query: str = "tobacco"):
        # eCFR 전용 헤더
        ecfr_headers = {
            "Referer": "https://www.ecfr.gov/",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Origin": "https://www.ecfr.gov"
        }
        
        super().__init__(headers=ecfr_headers)
        
        self.title_number = title_number
        self.query = query

    async def run(self) -> List[Dict[str, Any]]:
        print(f"🇺🇸 [API] eCFR Title {self.title_number} 검색 시작: '{self.query}'")
        
        params = {
            "query": self.query,
            "hierarchy[title]": self.title_number,
            "per_page": 50
        }

        try:
            response = await self.session.get(self.API_URL, params=params)
            
            if response.status_code != 200:
                try:
                    error_msg = response.json()
                except:
                    error_msg = response.text
                print(f"❌ API Error: {response.status_code} - {error_msg}")
                return []

            data = response.json()
            results = data.get("results", [])
            
            return self.parse(results, self.API_URL)

        except Exception as e:
            print(f"❌ eCFR API Connection Error: {e}")
            return []

    def parse(self, results: list, url: str) -> List[Dict[str, Any]]:
        parsed_data = []

        for item in results:
            try:
                hierarchy = item.get("hierarchy", {})
                title = hierarchy.get("title", "")
                section = hierarchy.get("section", "")
                
                # 제목 구성
                full_title = f"Title {title} Section {section}: {item.get('headline', '')}"
                date_str = item.get("last_modified_date") or datetime.now().strftime("%Y-%m-%d")
                
                # [핵심 수정] 뷰어 URL 대신 '데이터 렌더링 API URL' 생성
                # 예: https://www.ecfr.gov/api/renderer/v1/content/newest/title-27?region=section-1.1
                # 이 URL은 자바스크립트 없이도 순수한 규제 본문 HTML을 반환합니다.
                if title and section:
                    full_url = f"https://www.ecfr.gov/api/renderer/v1/content/newest/title-{title}?region=section-{section}"
                else:
                    # fallback (구조가 안 잡히면 일단 뷰어 URL)
                    short_url = item.get("structure_index_url", "")
                    full_url = f"https://www.ecfr.gov{short_url}"

                # API 데이터는 날짜가 바뀌면 새로운 내용이므로 해시에 날짜 포함
                unique_content = f"{full_title}{full_url}{date_str}"
                content_hash = self.generate_hash(unique_content)

                data = {
                    "country_code": "US",
                    "title": full_title,
                    "url": full_url, # 이제 여기가 API 주소가 됨
                    "proclaimed_date": date_str,
                    "hash_value": content_hash,
                    "source_type": "api"
                }
                parsed_data.append(data)

            except Exception as e:
                print(f"⚠️ Parsing Item Error: {e}")
                continue

        print(f"✅ [API] {len(parsed_data)}건 규제 정보 수신 완료")
        return parsed_data


# import httpx
# from typing import List, Dict, Any
# from datetime import datetime
# from app.crawler.crawling_regulation.base import BaseCrawler

# class ECFRAPICrawler(BaseCrawler):
#     API_URL = "https://www.ecfr.gov/api/search/v1/results"

#     def __init__(self, title_number: str = "21", query: str = "tobacco"):
#         # eCFR 전용 헤더 설정
#         ecfr_headers = {
#             "Referer": "https://www.ecfr.gov/",
#             "Upgrade-Insecure-Requests": "1",
#             "Sec-Fetch-Site": "same-origin",
#             "Sec-Fetch-Mode": "cors",
#             "Sec-Fetch-Dest": "empty",
#             "Origin": "https://www.ecfr.gov"
#         }
        
#         super().__init__(headers=ecfr_headers)
        
#         self.title_number = title_number
#         self.query = query

#     async def run(self) -> List[Dict[str, Any]]:
#         print(f"🇺🇸 [API] eCFR Title {self.title_number} 검색 시작: '{self.query}'")
        
#         # [수정됨] title -> hierarchy[title] 로 변경
#         # API가 계층 구조 필터링을 요구합니다.
#         params = {
#             "query": self.query,
#             "hierarchy[title]": self.title_number,  # <--- 핵심 수정 사항
#             "per_page": 50
#         }

#         try:
#             response = await self.session.get(self.API_URL, params=params)
            
#             if response.status_code != 200:
#                 # 에러 발생 시 상세 메시지를 출력해서 디버깅을 돕습니다.
#                 # json() 파싱 시도 후 실패하면 text 출력
#                 try:
#                     error_msg = response.json()
#                 except:
#                     error_msg = response.text
#                 print(f"❌ API Error: {response.status_code} - {error_msg}")
#                 return []

#             data = response.json()
#             results = data.get("results", [])
            
#             return self.parse(results, self.API_URL)

#         except Exception as e:
#             print(f"❌ eCFR API Connection Error: {e}")
#             return []

#     def parse(self, results: list, url: str) -> List[Dict[str, Any]]:
#         parsed_data = []

#         for item in results:
#             try:
#                 hierarchy = item.get("hierarchy", {})
#                 title = hierarchy.get("title", "")
#                 section = hierarchy.get("section", "")
                
#                 full_title = f"Title {title} Section {section}: {item.get('headline', '')}"
#                 date_str = item.get("last_modified_date") or datetime.now().strftime("%Y-%m-%d")
                
#                 short_url = item.get("structure_index_url", "")
#                 if short_url:
#                     full_url = f"https://www.ecfr.gov{short_url}"
#                 else:
#                     full_url = f"https://www.ecfr.gov/current/title-{self.title_number}"

#                 # API 데이터는 내용이 같아도 날짜가 갱신되면 새로운 것으로 쳐야 하므로 date_str을 해시에 포함
#                 unique_content = f"{full_title}{full_url}{date_str}"
#                 content_hash = self.generate_hash(unique_content)

#                 data = {
#                     "country_code": "US",
#                     "title": full_title,
#                     "url": full_url,
#                     "proclaimed_date": date_str,
#                     "hash_value": content_hash,
#                     "source_type": "api"
#                 }
#                 parsed_data.append(data)

#             except Exception as e:
#                 print(f"⚠️ Parsing Item Error: {e}")
#                 continue

#         print(f"✅ [API] {len(parsed_data)}건 규제 정보 수신 완료")
#         return parsed_data

# import httpx
# from typing import List, Dict, Any
# from datetime import datetime
# from app.crawler.crawling_regulation.base import BaseCrawler

# class ECFRAPICrawler(BaseCrawler):
#     API_URL = "https://www.ecfr.gov/api/search/v1/results"

#     def __init__(self, title_number: str = "21", query: str = "tobacco"):
#         ecfr_headers = {
#             "Referer": "https://www.ecfr.gov/",
#             "Upgrade-Insecure-Requests": "1",
#             "Sec-Fetch-Site": "same-origin",
#             "Sec-Fetch-Mode": "cors",
#             "Sec-Fetch-Dest": "empty",
#             "Origin": "https://www.ecfr.gov"
#         }
        
#         super().__init__(headers=ecfr_headers)
        
#         self.title_number = title_number
#         self.query = query

#     async def run(self) -> List[Dict[str, Any]]:
#         print(f"🇺🇸 [API] eCFR Title {self.title_number} 검색 시작: '{self.query}'")
        
#         # [수정됨] title -> titles (복수형), 값은 리스트로 전달
#         params = {
#             "query": self.query,
#             "titles": [self.title_number],  # <--- 여기가 핵심 수정 사항입니다.
#             "per_page": 50
#         }

#         try:
#             response = await self.session.get(self.API_URL, params=params)
            
#             if response.status_code != 200:
#                 # 에러 메시지 상세 출력
#                 print(f"❌ API Error: {response.status_code} - {response.text}")
#                 return []

#             data = response.json()
#             results = data.get("results", [])
            
#             return self.parse(results, self.API_URL)

#         except Exception as e:
#             print(f"❌ eCFR API Connection Error: {e}")
#             return []

#     def parse(self, results: list, url: str) -> List[Dict[str, Any]]:
#         parsed_data = []

#         for item in results:
#             try:
#                 hierarchy = item.get("hierarchy", {})
#                 title = hierarchy.get("title", "")
#                 section = hierarchy.get("section", "")
                
#                 full_title = f"Title {title} Section {section}: {item.get('headline', '')}"
#                 date_str = item.get("last_modified_date") or datetime.now().strftime("%Y-%m-%d")
                
#                 short_url = item.get("structure_index_url", "")
#                 if short_url:
#                     full_url = f"https://www.ecfr.gov{short_url}"
#                 else:
#                     full_url = f"https://www.ecfr.gov/current/title-{self.title_number}"

#                 unique_content = f"{full_title}{full_url}{date_str}"
#                 content_hash = self.generate_hash(unique_content)

#                 data = {
#                     "country_code": "US",
#                     "title": full_title,
#                     "url": full_url,
#                     "proclaimed_date": date_str,
#                     "hash_value": content_hash,
#                     "source_type": "api"
#                 }
#                 parsed_data.append(data)

#             except Exception as e:
#                 print(f"⚠️ Parsing Item Error: {e}")
#                 continue

#         print(f"✅ [API] {len(parsed_data)}건 규제 정보 수신 완료")
#         return parsed_data

# import httpx
# from typing import List, Dict, Any
# from datetime import datetime
# from app.crawler.crawling_regulation.base import BaseCrawler

# class ECFRAPICrawler(BaseCrawler):
#     API_URL = "https://www.ecfr.gov/api/search/v1/results"

#     def __init__(self, title_number: str = "21", query: str = "tobacco"):
#         # eCFR 전용 헤더 설정
#         ecfr_headers = {
#             "Referer": "https://www.ecfr.gov/",
#             "Upgrade-Insecure-Requests": "1",
#             "Sec-Fetch-Site": "same-origin",
#             "Sec-Fetch-Mode": "cors",
#             "Sec-Fetch-Dest": "empty",
#             "Origin": "https://www.ecfr.gov"
#         }
        
#         super().__init__(headers=ecfr_headers)
        
#         self.title_number = title_number
#         self.query = query

#     async def run(self) -> List[Dict[str, Any]]:
#         print(f"🇺🇸 [API] eCFR Title {self.title_number} 검색 시작: '{self.query}'")
        
#         # [수정됨] 400 에러를 유발하는 order, highlight 파라미터 제거
#         # eCFR API v1은 기본적으로 '관련도(Relevance)' 순으로 정렬됩니다.
#         params = {
#             "query": self.query,
#             "title": self.title_number,
#             "per_page": 50,  # 한 번에 가져올 개수
#             # "order": "newest",   <-- [삭제] 지원하지 않는 파라미터
#             # "highlight": "true"  <-- [삭제] 지원하지 않는 파라미터
#         }

#         try:
#             response = await self.session.get(self.API_URL, params=params)
            
#             if response.status_code != 200:
#                 # 에러 발생 시 상세 메시지를 출력해서 디버깅을 돕습니다.
#                 print(f"❌ API Error: {response.status_code} - {response.text}")
#                 return []

#             data = response.json()
#             results = data.get("results", [])
            
#             return self.parse(results, self.API_URL)

#         except Exception as e:
#             print(f"❌ eCFR API Connection Error: {e}")
#             return []

#     def parse(self, results: list, url: str) -> List[Dict[str, Any]]:
#         parsed_data = []

#         for item in results:
#             try:
#                 hierarchy = item.get("hierarchy", {})
#                 title = hierarchy.get("title", "")
#                 section = hierarchy.get("section", "")
                
#                 full_title = f"Title {title} Section {section}: {item.get('headline', '')}"
#                 date_str = item.get("last_modified_date") or datetime.now().strftime("%Y-%m-%d")
                
#                 short_url = item.get("structure_index_url", "")
#                 if short_url:
#                     full_url = f"https://www.ecfr.gov{short_url}"
#                 else:
#                     full_url = f"https://www.ecfr.gov/current/title-{self.title_number}"

#                 # API 데이터는 내용이 같아도 날짜가 갱신되면 새로운 것으로 쳐야 하므로 date_str을 해시에 포함
#                 unique_content = f"{full_title}{full_url}{date_str}"
#                 content_hash = self.generate_hash(unique_content)

#                 data = {
#                     "country_code": "US",
#                     "title": full_title,
#                     "url": full_url,
#                     "proclaimed_date": date_str,
#                     "hash_value": content_hash,
#                     "source_type": "api"
#                 }
#                 parsed_data.append(data)

#             except Exception as e:
#                 print(f"⚠️ Parsing Item Error: {e}")
#                 continue

#         print(f"✅ [API] {len(parsed_data)}건 규제 정보 수신 완료")
#         return parsed_data
