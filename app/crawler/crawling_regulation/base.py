import hashlib
from typing import Optional, Dict, Union
from curl_cffi.requests import AsyncSession

class UniversalFetcher:
    """
    [범용성 핵심]
    특정 사이트 전용 크롤러를 상속받아 만드는 부모 클래스가 아니라,
    Discovery Agent가 URL을 발견하면 즉시 출동해서 데이터를 가져오는 '독립 실행형 도구'입니다.
    """
    def __init__(self, headers: Optional[Dict[str, str]] = None):
        # 기본 헤더: 범용성을 위해 일반적인 브라우저처럼 위장
        default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        if headers:
            default_headers.update(headers)

        # impersonate="chrome120": 클라우드플레어 등 보안 솔루션 우회에 필수
        self.session = AsyncSession(
            impersonate="chrome120", 
            headers=default_headers,
            timeout=30,
            verify=False # SSL 에러 무시 (오래된 정부 사이트 호환성)
        )

    def generate_hash(self, content: Union[str, bytes]) -> str:
        """데이터 중복 체크를 위한 해시 생성"""
        if isinstance(content, str):
            content = content.encode('utf-8')
        return hashlib.sha256(content).hexdigest()

    async def fetch(self, url: str) -> Optional[str]:
        """HTML 텍스트 가져오기 (웹페이지용)"""
        try:
            print(f"🌐 Fetching URL: {url}")
            response = await self.session.get(url)
            
            # 4xx, 5xx 에러 처리
            if response.status_code >= 400:
                print(f"❌ Fetch Failed [{url}] (Status: {response.status_code})")
                return None
            
            # 인코딩 자동 감지 및 텍스트 반환
            return response.text
            
        except Exception as e:
            print(f"❌ Fetch Error [{url}]: {e}")
            return None

    async def fetch_binary(self, url: str) -> Optional[bytes]:
        """PDF, DOCX 등 바이너리 파일 다운로드 (문서용)"""
        try:
            print(f"⬇️ Downloading Binary: {url}")
            response = await self.session.get(url)
            
            if response.status_code == 200:
                return response.content
            else:
                print(f"❌ Download Failed Status: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Binary Fetch Error: {e}")
            return None

    async def close(self):
        """세션 종료"""
        await self.session.close()

# import hashlib
# from abc import ABC, abstractmethod
# from typing import Optional, Dict, Any
# from curl_cffi.requests import AsyncSession

# class BaseCrawler(ABC):
#     # headers 인자를 받을 수 있도록 수정
#     def __init__(self, headers: Optional[Dict[str, str]] = None):
#         # 기본 헤더 (모든 크롤러 공통)
#         default_headers = {
#             "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
#             "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
#             "Accept-Language": "en-US,en;q=0.9",
#         }
        
#         # 특정 크롤러에서 헤더를 추가했으면 병합 (Update)
#         if headers:
#             default_headers.update(headers)

#         # [유지] impersonate 버전은 최신(chrome120)으로 유지해도 다른 사이트에 해가 되지 않습니다.
#         self.session = AsyncSession(
#             impersonate="chrome120", 
#             headers=default_headers,
#             timeout=30
#         )

#     def generate_hash(self, content: str) -> str:
#         return hashlib.sha256(content.encode('utf-8')).hexdigest()

#     async def fetch(self, url: str) -> Optional[str]:
#         """HTML 텍스트 가져오기"""
#         try:
#             response = await self.session.get(url)
            
#             if response.status_code in [403, 404, 406, 429]:
#                 print(f"❌ Blocked or Not Found [{url}] (Status: {response.status_code})")
#                 return None
            
#             # [일반화] 특정 사이트 에러 체크 로직 제거 (각 크롤러에서 처리 권장)
#             return response.text
#         except Exception as e:
#             print(f"❌ Fetch Error [{url}]: {e}")
#             return None

#     async def fetch_binary(self, url: str) -> Optional[bytes]:
#         try:
#             print(f"⬇️ Downloading: {url}")
#             response = await self.session.get(url)
#             if response.status_code == 200:
#                 return response.content
#             else:
#                 print(f"❌ Download Failed Status: {response.status_code}")
#                 return None
#         except Exception as e:
#             print(f"❌ Binary Fetch Error: {e}")
#             return None

#     @abstractmethod
#     async def parse(self, html: str, url: str) -> Dict[str, Any]:
#         pass

#     async def close(self):
#         await self.session.close()

# # app/crawler/base.py

# import hashlib
# from abc import ABC, abstractmethod
# from typing import Optional, Dict, Any
# from curl_cffi.requests import AsyncSession

# class BaseCrawler(ABC):
#     def __init__(self):
#         # 파일 다운로드를 위해 impersonate 유지
#         self.session = AsyncSession(impersonate="chrome110") 

#     def generate_hash(self, content: str) -> str:
#         return hashlib.sha256(content.encode('utf-8')).hexdigest()

#     async def fetch(self, url: str) -> Optional[str]:
#         """HTML 텍스트 가져오기"""
#         try:
#             response = await self.session.get(url)
#             if response.status_code in [403, 404]:
#                 print(f"❌ Blocked or Not Found [{url}]")
#                 return None
#             return response.text
#         except Exception as e:
#             print(f"❌ Fetch Error [{url}]: {e}")
#             return None

#     # [추가됨] 파일 다운로드를 위한 메서드
#     async def fetch_binary(self, url: str) -> Optional[bytes]:
#         """PDF 등 바이너리 데이터 가져오기"""
#         try:
#             print(f"⬇️ Downloading: {url}")
#             response = await self.session.get(url)
#             if response.status_code == 200:
#                 return response.content
#             else:
#                 print(f"❌ Download Failed Status: {response.status_code}")
#                 return None
#         except Exception as e:
#             print(f"❌ Binary Fetch Error: {e}")
#             return None

#     @abstractmethod
#     async def parse(self, html: str, url: str) -> Dict[str, Any]:
#         pass

#     async def close(self):
#         await self.session.close()