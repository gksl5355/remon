# app/ai_pipeline/preprocess/loader.py

import os
import aiofiles # 비동기 읽기 지원을 위해 변경하면 좋지만, 로직 단순화를 위해 일단 동기 open 사용
from pypdf import PdfReader
from bs4 import BeautifulSoup

class DocumentLoader:
    @staticmethod
    def load_pdf(file_path: str) -> str:
        """PDF 파일에서 텍스트 추출"""
        text_content = []
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_content.append(text)
            return "\n".join(text_content)
        except Exception as e:
            print(f"❌ PDF Load Error: {e}")
            return ""

    @staticmethod
    def load_html(file_path: str) -> str:
        """HTML 파일에서 텍스트 추출 (기존 유지)"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'lxml')
                for script in soup(["script", "style"]):
                    script.extract()
                return soup.get_text(separator='\n', strip=True)
        except Exception as e:
            print(f"❌ HTML Load Error: {e}")
            return ""

    # [추가] .txt 파일 로더
    @staticmethod
    def load_txt(file_path: str) -> str:
        """단순 텍스트 파일 읽기"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"❌ TXT Load Error: {e}")
            return ""

    @staticmethod
    def load(file_path: str) -> str:
        """확장자에 따라 적절한 로더 호출"""
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == ".pdf":
            return DocumentLoader.load_pdf(file_path)
        elif ext in [".html", ".htm"]:
            return DocumentLoader.load_html(file_path)
        elif ext == ".txt": # [추가] txt 지원
            return DocumentLoader.load_txt(file_path)
        else:
            print(f"⚠️ 지원하지 않는 파일 형식: {ext}")
            return ""