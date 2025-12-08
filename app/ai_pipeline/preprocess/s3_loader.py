"""
module: s3_loader.py
description: S3에서 오늘 날짜 규제 파일 자동 로드 (전처리 통합)
author: AI Agent
created: 2025-01-19
updated: 2025-01-19
dependencies:
    - app.utils.s3_client
    - boto3
"""

import logging
from typing import List, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class S3RegulationLoader:
    """S3에서 규제 파일 자동 로드"""
    
    def __init__(self):
        from app.utils.s3_client import S3Client
        self.s3_client = S3Client()
    
    def get_today_files(self, date: Optional[str] = None) -> List[str]:
        """
        오늘 날짜의 S3 규제 파일 목록 조회.
        
        Args:
            date: YYYYMMDD 형식 (None이면 오늘)
            
        Returns:
            S3 키 리스트 (예: ["regulation/US/20250119_file.pdf"])
        """
        target_date = date or datetime.now().strftime("%Y%m%d")
        
        logger.info(f"📅 S3 규제 파일 검색: {target_date}")
        
        s3_keys = self.s3_client.get_today_regulation_files(target_date)
        
        logger.info(f"✅ 발견된 파일: {len(s3_keys)}개")
        for key in s3_keys:
            logger.info(f"   - {key}")
        
        return s3_keys
    
    def download_to_temp(self, s3_key: str) -> str:
        """
        S3 파일을 /tmp에 다운로드.
        
        Args:
            s3_key: S3 객체 키
            
        Returns:
            로컬 임시 파일 경로
        """
        logger.info(f"📥 S3 다운로드: {s3_key}")
        
        temp_path = self.s3_client.download_to_temp(s3_key)
        
        logger.info(f"✅ 다운로드 완료: {temp_path}")
        return temp_path
    
    def cleanup_temp(self, temp_path: str):
        """임시 파일 삭제"""
        import os
        if os.path.exists(temp_path):
            os.remove(temp_path)
            logger.debug(f"🗑️ 임시 파일 삭제: {temp_path}")


def load_today_regulations(date: Optional[str] = None) -> List[str]:
    """
    오늘 날짜 규제 파일을 S3에서 다운로드하여 로컬 경로 반환.
    
    Args:
        date: YYYYMMDD 형식 (None이면 오늘)
        
    Returns:
        다운로드된 로컬 파일 경로 리스트
    """
    loader = S3RegulationLoader()
    
    # S3 파일 목록 조회
    s3_keys = loader.get_today_files(date)
    
    if not s3_keys:
        logger.warning(f"⚠️ {date or 'today'} 규제 파일 없음")
        return []
    
    # 다운로드
    local_paths = []
    for s3_key in s3_keys:
        try:
            temp_path = loader.download_to_temp(s3_key)
            local_paths.append(temp_path)
        except Exception as e:
            logger.error(f"❌ 다운로드 실패 ({s3_key}): {e}")
    
    return local_paths


__all__ = ["S3RegulationLoader", "load_today_regulations"]
