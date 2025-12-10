"""
module: s3_loader.py
description: S3에서 오늘 날짜 규제 파일 자동 로드 (전처리 통합)
author: AI Agent
created: 2025-01-19
updated: 2025-12-10
dependencies:
    - boto3
"""

import logging
import os
import uuid
from typing import List, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class S3RegulationLoader:
    """S3에서 규제 파일 자동 로드"""
    
    def __init__(self, s3_prefix: str = "skala2/skala-2.4.17/test"):
        import boto3
        self.s3_client = boto3.client('s3')
        self.bucket = "arn:aws:s3:ap-northeast-2:881490135253:accesspoint/sk-team-storage"
        self.s3_prefix = s3_prefix
    
    def get_today_files(self, date: Optional[str] = None) -> List[str]:
        """
        오늘 업로드된 S3 PDF 파일 목록 조회 (LastModified 기준).
        
        Args:
            date: YYYY-MM-DD 형식 (None이면 오늘)
            
        Returns:
            S3 키 리스트 (예: ["skala2/skala-2.4.17/test/US/file.pdf"])
        """
        from datetime import datetime, timezone
        
        # 대상 날짜 (UTC 기준)
        if date:
            target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            target_date = datetime.now(timezone.utc)
        
        # 오늘 시작 시각 (00:00:00 UTC)
        today_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        logger.info(f"📅 S3 파일 검색: {self.s3_prefix} (날짜: {today_start.date()})")
        
        # S3 객체 목록 조회
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=self.s3_prefix
            )
        except Exception as e:
            logger.error(f"❌ S3 조회 실패: {e}")
            return []
        
        if 'Contents' not in response:
            logger.warning(f"⚠️ {self.s3_prefix}에 파일 없음")
            return []
        
        # 오늘 업로드된 PDF 파일만 필터링
        today_files = []
        for obj in response['Contents']:
            key = obj['Key']
            last_modified = obj['LastModified']
            
            # PDF 파일이고 오늘 업로드된 것만
            if key.lower().endswith('.pdf') and last_modified >= today_start:
                today_files.append(key)
                logger.info(f"   ✅ {key} (업로드: {last_modified})")
        
        logger.info(f"✅ 발견된 파일: {len(today_files)}개")
        return today_files
    
    def download_to_temp(self, s3_key: str) -> str:
        """
        S3 파일을 /tmp에 다운로드.
        
        Args:
            s3_key: S3 객체 키
            
        Returns:
            로컬 임시 파일 경로
        """
        logger.info(f"📥 S3 다운로드: {s3_key}")
        
        # 임시 파일 경로 생성 (UUID로 충돌 방지)
        file_ext = Path(s3_key).suffix
        temp_filename = f"{uuid.uuid4().hex}{file_ext}"
        temp_path = os.path.join("/tmp", temp_filename)
        
        # S3에서 다운로드
        self.s3_client.download_file(self.bucket, s3_key, temp_path)
        
        logger.info(f"✅ 다운로드 완료: {temp_path}")
        return temp_path
    
    def cleanup_temp(self, temp_path: str):
        """임시 파일 삭제"""
        import os
        if os.path.exists(temp_path):
            os.remove(temp_path)
            logger.debug(f"🗑️ 임시 파일 삭제: {temp_path}")


def load_today_regulations(
    date: Optional[str] = None, 
    s3_prefix: str = "skala2/skala-2.4.17/test"
) -> List[str]:
    """
    오늘 업로드된 규제 파일을 S3에서 다운로드하여 로컬 경로 반환.
    
    Args:
        date: YYYY-MM-DD 형식 (None이면 오늘)
        s3_prefix: S3 프리픽스 (기본값: skala2/skala-2.4.17/test)
        
    Returns:
        다운로드된 로컬 파일 경로 리스트
    """
    loader = S3RegulationLoader(s3_prefix=s3_prefix)
    
    # S3 파일 목록 조회 (오늘 업로드된 것만)
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
