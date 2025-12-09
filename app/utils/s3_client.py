"""
module: s3_client.py
description: S3 규제 파일 관리 클라이언트 (PDF/TXT 다운로드)
author: AI Agent
created: 2025-01-18
updated: 2025-01-19
"""

import logging
import json
import boto3
import os
import re
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from io import BytesIO

logger = logging.getLogger(__name__)


class S3Client:
    """S3 규제 파일 관리 클라이언트"""

    def __init__(
        self,
        access_key_id: str = None,
        secret_access_key: str = None,
        region: str = None,
        bucket_arn: str = None,
    ):
        # 환경변수에서 로드
        access_key_id = access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        secret_access_key = secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        region = region or os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")
        bucket_arn = bucket_arn or os.getenv("AWS_S3_ACCESS_POINT_ARN")

        if not access_key_id or not secret_access_key:
            raise ValueError(
                "AWS 자격 증명 필요: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY 환경변수 설정"
            )
        if not bucket_arn:
            raise ValueError("AWS_S3_ACCESS_POINT_ARN 환경변수 설정 필요")

        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )
        self.bucket_arn = bucket_arn
        self.regulation_base = f"{os.getenv('S3_BASE_PREFIX')}/{os.getenv('S3_APP_PREFIX')}/regulation/US/"
        logger.info(f"✅ S3 클라이언트 초기화: {bucket_arn}")

    def download_to_temp(self, s3_key: str) -> str:
        """
        S3 파일을 /tmp에 다운로드.
        
        Args:
            s3_key: S3 키 (regulation/US/file.pdf)
            
        Returns:
            임시 파일 경로
        """
        import uuid
        
        filename = Path(s3_key).name
        temp_path = f"/tmp/{uuid.uuid4()}_{filename}"
        
        try:
            self.s3.download_file(self.bucket_arn, s3_key, temp_path)
            logger.info(f"✅ S3 다운로드: {s3_key} → {temp_path}")
            return temp_path
        except Exception as e:
            logger.error(f"❌ S3 다운로드 실패: {e}")
            raise
    
    def get_today_regulation_files(self, date_str: str = None) -> List[str]:
        """
        특정 날짜의 규제 파일 목록 조회.
        
        Args:
            date_str: YYYYMMDD 형식 (기본값: 오늘)
            
        Returns:
            S3 키 리스트
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y%m%d")
        
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_arn,
                Prefix=self.regulation_base
            )
            
            if "Contents" not in response:
                logger.warning(f"⚠️ S3 경로에 파일 없음: {self.regulation_base}")
                return []
            
            # 날짜 패턴 매칭 (YYYYMMDD)
            date_pattern = re.compile(rf"_{date_str}\.pdf$")
            
            matched_files = []
            for obj in response["Contents"]:
                s3_key = obj["Key"]
                if date_pattern.search(s3_key):
                    matched_files.append(s3_key)
            
            logger.info(f"✅ {date_str} 규제 파일: {len(matched_files)}개")
            return matched_files
            
        except Exception as e:
            logger.error(f"❌ S3 파일 목록 조회 실패: {e}")
            return []
    
    def parse_s3_uri(self, uri: str) -> tuple[str, str]:
        """
        S3 URI 파싱.
        
        Args:
            uri: s3://bucket/key 또는 arn:aws:s3:...
            
        Returns:
            (bucket_arn, key)
        """
        if uri.startswith("arn:aws:s3:"):
            # arn:aws:s3:region:account:accesspoint/name/key
            parts = uri.split("/", 1)
            if len(parts) == 2:
                return self.bucket_arn, parts[1]
            return self.bucket_arn, ""
        elif uri.startswith("s3://"):
            # s3://bucket/key
            uri = uri[5:]
            parts = uri.split("/", 1)
            if len(parts) == 2:
                return parts[0], parts[1]
            return parts[0], ""
        else:
            # 상대 경로로 간주
            return self.bucket_arn, uri
