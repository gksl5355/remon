# app/crawler/base.py

import hashlib
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from curl_cffi.requests import AsyncSession

class BaseCrawler(ABC):
    def __init__(self):
        # 파일 다운로드를 위해 impersonate 유지
        self.session = AsyncSession(impersonate="chrome110") 

    def generate_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    async def fetch(self, url: str) -> Optional[str]:
        """HTML 텍스트 가져오기"""
        try:
            response = await self.session.get(url)
            if response.status_code in [403, 404]:
                print(f"❌ Blocked or Not Found [{url}]")
                return None
            return response.text
        except Exception as e:
            print(f"❌ Fetch Error [{url}]: {e}")
            return None

    # [추가됨] 파일 다운로드를 위한 메서드
    async def fetch_binary(self, url: str) -> Optional[bytes]:
        """PDF 등 바이너리 데이터 가져오기"""
        try:
            print(f"⬇️ Downloading: {url}")
            response = await self.session.get(url)
            if response.status_code == 200:
                return response.content
            else:
                print(f"❌ Download Failed Status: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Binary Fetch Error: {e}")
            return None

    @abstractmethod
    async def parse(self, html: str, url: str) -> Dict[str, Any]:
        pass

    async def close(self):
        await self.session.close()