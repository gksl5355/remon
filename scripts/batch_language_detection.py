"""
기존 데이터셋에 대한 일괄 언어 탐지
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import json

# 프로젝트 루트에서 app 폴더 접근
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.crawler.cleaner import get_language_detector
from app.utils.text_utils import update_metadata_with_language, save_metadata

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('language_detection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BatchLanguageDetector:
    """배치 언어 탐지 처리 클래스"""
    
    def __init__(self, data_directory: str):
        """
        초기화
        
        Args:
            data_directory: 데이터 디렉토리 경로
        """
        self.data_dir = Path(data_directory)
        self.detector = get_language_detector()
        
        self.results = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'details': [],
            'start_time': datetime.now().isoformat(),
            'end_time': None
        }
    
    def find_metadata_files(self) -> List[Path]:
        """
        디렉토리에서 메타데이터 파일 찾기
        
        Returns:
            메타데이터 파일 경로 리스트
        """
        metadata_files = list(self.data_dir.rglob("*_metadata.json"))
        logger.info(f"발견된 메타데이터 파일: {len(metadata_files)}개")
        return metadata_files
    
    def process_file(self, metadata_path: Path) -> Dict:
        """
        개별 파일 처리
        
        Args:
            metadata_path: 메타데이터 파일 경로
            
        Returns:
            처리 결과
        """
        result = {
            'file': str(metadata_path.name),
            'status': 'unknown',
            'original_lang': None,
            'detected_lang': None,
            'confidence': 0.0,
            'error': None
        }
        
        try:
            # 1. 대응하는 .txt 파일 찾기
            text_file = metadata_path.parent / metadata_path.name.replace('_metadata.json', '.txt')
            
            if not text_file.exists():
                logger.warning(f"텍스트 파일 없음: {text_file.name}")
                result['status'] = 'skipped'
                result['error'] = 'Text file not found'
                self.results['skipped'] += 1
                return result
            
            # 2. 기존 메타데이터 로드
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            original_lang = metadata.get('metadata', {}).get('language_code')
            country_code = metadata.get('metadata', {}).get('country_code')
            result['original_lang'] = original_lang
            
            # 3. 언어 탐지 및 업데이트
            updated_metadata = update_metadata_with_language(
                str(metadata_path),
                str(text_file),
                self.detector,
                country_code=country_code,
                backup=True
            )
            
            # 4. 저장
            save_metadata(updated_metadata, str(metadata_path))
            
            detected_info = updated_metadata['metadata']['language_detection']
            result['status'] = 'success'
            result['detected_lang'] = detected_info['detected_language']
            result['confidence'] = detected_info['confidence']
            result['is_reliable'] = detected_info.get('is_reliable', False)
            
            self.results['success'] += 1
            
            logger.info(
                f"✓ {metadata_path.name}: {original_lang} -> {result['detected_lang']} "
                f"(신뢰도: {result['confidence']:.2%})"
            )
            
        except Exception as e:
            logger.error(f"✗ {metadata_path.name}: {e}", exc_info=True)
            result['status'] = 'failed'
            result['error'] = str(e)
            self.results['failed'] += 1
        
        return result
    
    def run(self, max_files: int = None) -> Dict:
        """
        배치 처리 실행
        
        Args:
            max_files: 처리할 최대 파일 수 (None이면 전체)
            
        Returns:
            처리 결과 요약
        """
        logger.info(f"배치 언어 탐지 시작: {self.data_dir}")
        
        # 메타데이터 파일 찾기
        metadata_files = self.find_metadata_files()
        
        if not metadata_files:
            logger.warning("처리할 메타데이터 파일이 없습니다.")
            return self.results
        
        # 최대 파일 수 제한
        if max_files:
            metadata_files = metadata_files[:max_files]
        
        self.results['total'] = len(metadata_files)
        
        # 처리
        try:
            from tqdm import tqdm
            iterator = tqdm(metadata_files, desc="언어 탐지 진행")
        except ImportError:
            iterator = metadata_files
            logger.info("tqdm 미설치 - 진행 표시 없이 처리")
        
        for metadata_path in iterator:
            result = self.process_file(metadata_path)
            self.results['details'].append(result)
        
        # 종료 시간 기록
        self.results['end_time'] = datetime.now().isoformat()
        
        # 결과 요약 출력
        self._print_summary()
        
        # 결과 저장
        self._save_results()
        
        return self.results
    
    def _print_summary(self):
        """결과 요약 출력"""
        print("\n" + "="*60)
        print("언어 탐지 배치 처리 결과")
        print("="*60)
        print(f"전체 파일:     {self.results['total']}")
        print(f"성공:          {self.results['success']}")
        print(f"실패:          {self.results['failed']}")
        print(f"건너뜀:        {self.results['skipped']}")
        
        if self.results['total'] > 0:
            success_rate = self.results['success'] / self.results['total'] * 100
            print(f"성공률:        {success_rate:.1f}%")
        
        print("="*60)
        
        # 언어 변경 통계
        lang_changes = {}
        for detail in self.results['details']:
            if detail['status'] == 'success':
                original = detail['original_lang'] or 'None'
                detected = detail['detected_lang']
                key = f"{original} → {detected}"
                lang_changes[key] = lang_changes.get(key, 0) + 1
        
        if lang_changes:
            print("\n언어 변경 통계:")
            for change, count in sorted(lang_changes.items(), key=lambda x: x[1], reverse=True):
                print(f"  {change}: {count}개")
        
        # 신뢰도 낮은 파일 표시
        low_confidence = [
            d for d in self.results['details'] 
            if d['status'] == 'success' and not d.get('is_reliable', True)
        ]
        
        if low_confidence:
            print(f"\n신뢰도 낮은 파일 ({len(low_confidence)}개):")
            for detail in low_confidence[:5]:  # 최대 5개만 표시
                print(f"  - {detail['file']}: {detail['detected_lang']} ({detail['confidence']:.2%})")
            
            if len(low_confidence) > 5:
                print(f"  ... 외 {len(low_confidence) - 5}개")
        
        print("\n")
    
    def _save_results(self):
        """결과를 JSON 파일로 저장"""
        output_file = Path('language_detection_results.json')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"결과 저장 완료: {output_file}")


def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='배치 언어 탐지 스크립트',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 전체 처리
  python scripts/batch_language_detection.py /path/to/data
  
  # 처음 10개만 테스트
  python scripts/batch_language_detection.py /path/to/data --max-files 10
        """
    )
    
    parser.add_argument(
        'data_dir',
        type=str,
        help='데이터 디렉토리 경로'
    )
    parser.add_argument(
        '--max-files',
        type=int,
        default=None,
        help='처리할 최대 파일 수 (테스트용)'
    )
    
    args = parser.parse_args()
    
    # 디렉토리 존재 확인
    data_path = Path(args.data_dir)
    if not data_path.exists():
        print(f"오류: 디렉토리를 찾을 수 없습니다: {args.data_dir}")
        sys.exit(1)
    
    # 배치 처리 실행
    batch_detector = BatchLanguageDetector(args.data_dir)
    results = batch_detector.run(max_files=args.max_files)
    
    # 실패한 파일이 있으면 종료 코드 1 반환
    if results['failed'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
