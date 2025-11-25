#!/usr/bin/env python
"""Vision Pipeline 빠른 테스트 (첫 2페이지만)"""

import asyncio
import logging
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.ai_pipeline.preprocess.vision_ingestion import PDFRenderer, ComplexityAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_basic():
    """기본 렌더링 및 복잡도 분석 테스트"""
    
    pdf_path = project_root / "app/ai_pipeline/preprocess/demo/ⓕ2.담배 및 기타 특정 연소 담배 제품의 니코틴 함량에 대한 담배 제품 표준_2025-00397_FDA.pdf"
    
    if not pdf_path.exists():
        logger.error(f"PDF 파일 없음: {pdf_path}")
        return
    
    logger.info(f"테스트 대상: {pdf_path.name}")
    
    # 1. 렌더링 테스트
    renderer = PDFRenderer(dpi=150)  # 낮은 DPI로 빠르게
    pages = renderer.render_pages(str(pdf_path), page_range=(0, 2))
    
    logger.info(f"✅ 렌더링 완료: {len(pages)}페이지")
    
    # 2. 복잡도 분석 테스트
    analyzer = ComplexityAnalyzer()
    for page in pages:
        complexity = analyzer.analyze_page(str(pdf_path), page["page_num"])
        logger.info(
            f"페이지 {page['page_num']}: "
            f"복잡도={complexity['complexity_score']:.2f}, "
            f"표={complexity['table_count']}개"
        )
    
    logger.info("✅ 기본 테스트 완료")


if __name__ == "__main__":
    asyncio.run(test_basic())
