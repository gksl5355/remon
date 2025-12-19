#!/usr/bin/env python
"""
strategy_data.pdf를 전처리하여 skala-2.4.17-strategy 컬렉션에 임베딩
updated: 2025-01-23

Usage:
    uv run python scripts/embed_ktng_strategies.py
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from app.ai_pipeline.tools.strategy_history import StrategyHistoryTool
import PyPDF2


def extract_text_from_pdf(pdf_path: Path) -> str:
    """PDF에서 텍스트 추출"""
    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text


def split_into_chunks(text: str, chunk_size: int = 1000) -> list:
    """텍스트를 청크로 분할 (간단한 방식)"""
    chunks = []
    lines = text.split('\n')
    current_chunk = []
    current_size = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        line_size = len(line)
        
        if current_size + line_size > chunk_size and current_chunk:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [line]
            current_size = line_size
        else:
            current_chunk.append(line)
            current_size += line_size
    
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    return chunks


def main():
    print("=" * 60)
    print("🚀 strategy_data.pdf 전처리 및 임베딩")
    print("=" * 60)
    
    pdf_path = project_root / "regulation_file" / "stragey_data.pdf"
    
    if not pdf_path.exists():
        print(f"❌ PDF 파일 없음: {pdf_path}")
        return
    
    print(f"📄 PDF 파일: {pdf_path}")
    print(f"📦 컬렉션: skala-2.4.17-strategy")
    print()
    
    # PDF 텍스트 추출
    print("📖 PDF 텍스트 추출 중...")
    text = extract_text_from_pdf(pdf_path)
    print(f"✅ 추출 완료: {len(text)} chars")
    print()
    
    # 텍스트를 청크로 분할
    print("✂️ 텍스트 청크 분할 중...")
    chunks = split_into_chunks(text, chunk_size=800)
    print(f"✅ 분할 완료: {len(chunks)}개 청크")
    print()
    
    if not chunks:
        print("⚠️ 청크 없음")
        return
    
    # StrategyHistoryTool 초기화
    tool = StrategyHistoryTool(collection="skala-2.4.17-strategy")
    
    # 컬렉션 생성 (없으면)
    print("📦 컬렉션 확인 중...")
    tool.ensure_collection()
    print("✅ 컬렉션 준비 완료")
    print()
    
    # 각 청크를 전략으로 저장
    for i, chunk in enumerate(chunks, 1):
        print(f"[{i}/{len(chunks)}] 청크 처리 중...")
        print(f"   내용: {chunk[:80]}...")
        
        try:
            # 청크를 규제 요약으로, 전체 내용을 전략으로 저장
            tool.save_strategy_history(
                regulation_summary=chunk[:200],  # 앞 200자를 요약으로
                mapped_products=["Strategy Document"],
                strategies=[chunk]  # 전체 청크를 전략으로
            )
            
            print(f"   ✅ 저장 완료")
        except Exception as e:
            print(f"   ❌ 실패: {e}")
            import traceback
            traceback.print_exc()
        
        print()
    
    print("=" * 60)
    print("✅ 임베딩 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
