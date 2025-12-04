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

