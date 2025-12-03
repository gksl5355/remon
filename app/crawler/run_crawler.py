"""
PDF 언어 감지 크롤러 실행 스크립트
"""

import json
import logging
from pathlib import Path
from typing import List, Dict
from .pdf_language_detector import PDFLanguageDetector


def detect_pdf_language(pdf_path: str) -> str:
    """
    PDF 파일의 언어를 감지하여 언어 코드를 반환
    
    Args:
        pdf_path: PDF 파일 경로
        
    Returns:
        언어 코드 (예: "EN", "ID", "RU", "UNKNOWN", "ERROR")
    """
    detector = PDFLanguageDetector()
    result = detector.process_pdf(pdf_path)
    return result['language_code']


# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_test_pdf_files() -> List[str]:
    """테스트용 PDF 파일 경로 반환"""
    base_path = Path(__file__).parent.parent.parent / "regulation_file"
    
    test_files = [
        base_path / "id" / "practice_id.pdf",
        base_path / "us" / "practice_us.pdf", 
        base_path / "rs" / "practice_rs.pdf"
    ]
    
    return [str(f) for f in test_files]


def process_pdf_files(pdf_files: List[str]) -> List[Dict[str, any]]:
    """
    PDF 파일들을 처리하여 언어 감지 수행
    
    Args:
        pdf_files: PDF 파일 경로 리스트
        
    Returns:
        처리 결과 리스트
    """
    detector = PDFLanguageDetector()
    results = []
    
    for pdf_path in pdf_files:
        logger.info(f"Processing: {pdf_path}")
        
        result = detector.process_pdf(pdf_path)
        
        # 결과 로깅
        if result['success']:
            logger.info(
                f"✓ {Path(pdf_path).name}: "
                f"{result['language_code']} ({result['language_name']}) "
                f"- 신뢰도: {result['confidence']:.2%} "
                f"- 페이지: {result['total_pages']}장 "
                f"(샘플: {result['sample_pages']})"
            )
        else:
            logger.error(f"✗ {Path(pdf_path).name}: {result['error']}")
        
        results.append(result)
    
    return results


def format_results(results: List[Dict[str, any]]) -> List[Dict[str, str]]:
    """
    결과를 요구사항 형식으로 포맷팅
    
    Args:
        results: 처리 결과 리스트
        
    Returns:
        포맷팅된 결과 리스트
    """
    formatted = []
    
    for result in results:
        formatted_result = {
            "file_path": result['file_path'],
            "language_code": result['language_code'],
            "language_name": result['language_name']
        }
        formatted.append(formatted_result)
    
    return formatted


def main(verbose: bool = False):
    """메인 실행 함수"""
    logger.info("PDF 언어 감지 크롤러 시작")
    
    # 테스트 PDF 파일 목록
    pdf_files = get_test_pdf_files()
    
    logger.info(f"처리할 PDF 파일 수: {len(pdf_files)}")
    for pdf_path in pdf_files:
        logger.info(f"  - {pdf_path}")
    
    # PDF 처리
    results = process_pdf_files(pdf_files)
    
    # 결과 포맷팅
    formatted_results = format_results(results)
    
    # 최종 결과 출력
    print("\n" + "="*60)
    print("PDF 언어 감지 결과")
    print("="*60)
    
    for i, (result, detailed) in enumerate(zip(formatted_results, results)):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        if verbose and detailed['success']:
            print(f"상세 정보:")
            print(f"  - 전체 페이지: {detailed['total_pages']}장")
            print(f"  - 샘플 페이지: {detailed['sample_pages']}")
            print(f"  - 추출 텍스트 길이: {detailed['text_length']:,}자")
            print(f"  - 신뢰도: {detailed['confidence']:.2%}")
            print(f"  - 신뢰성: {'높음' if detailed['is_reliable'] else '낮음'}")
        
        print("-" * 40)
    
    # 요약 통계
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    
    print(f"\n처리 완료: 성공 {successful}개, 실패 {failed}개")
    
    logger.info("PDF 언어 감지 크롤러 완료")


if __name__ == "__main__":
    import sys
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    main(verbose=verbose)