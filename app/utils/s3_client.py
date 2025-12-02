"""
module: s3_client.py
description: S3 JSON 파일 업로드/다운로드 클라이언트
author: AI Agent
created: 2025-01-18
"""

import logging
import json
import boto3
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


class S3Client:
    """S3 JSON 파일 관리 클라이언트"""

    def __init__(
        self,
        access_key_id: str = None,
        secret_access_key: str = None,
        region: str = "ap-northeast-2",
        bucket_arn: str = "arn:aws:s3:ap-northeast-2:881490135253:accesspoint/sk-team-storage",
        base_prefix: str = "skala-2.4.17/preprocessed_jsons/",
    ):
        import os

        # 환경변수에서 로드
        access_key_id = access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        secret_access_key = secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")

        if not access_key_id or not secret_access_key:
            raise ValueError(
                "AWS 자격 증명 필요: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY 환경변수 설정"
            )

        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )
        self.bucket_arn = bucket_arn
        self.base_prefix = base_prefix
        logger.info(f"✅ S3 클라이언트 초기화: {bucket_arn}/{base_prefix}")

    def upload_json(self, json_path: str, s3_key: Optional[str] = None) -> str:
        """JSON 파일을 S3에 업로드"""
        json_file = Path(json_path)

        if not s3_key:
            s3_key = f"{self.base_prefix}{json_file.name}"

        try:
            self.s3.upload_file(str(json_file), self.bucket_arn, s3_key)
            logger.info(f"✅ S3 업로드: {s3_key}")
            return s3_key
        except Exception as e:
            logger.error(f"❌ S3 업로드 실패: {e}")
            raise

    def download_json(self, s3_key: str, local_path: str) -> str:
        """S3에서 JSON 파일 다운로드"""
        try:
            self.s3.download_file(self.bucket_arn, s3_key, local_path)
            logger.info(f"✅ S3 다운로드: {s3_key} → {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"❌ S3 다운로드 실패: {e}")
            raise

    def search_json_by_metadata(
        self,
        title: Optional[str] = None,
        country: Optional[str] = None,
        regulation_type: Optional[str] = None,
    ) -> List[dict]:
        """메타데이터 기반 JSON 파일 검색"""
        try:
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_arn, Prefix=self.base_prefix
            )

            if "Contents" not in response:
                return []

            matched_files = []

            for obj in response["Contents"]:
                s3_key = obj["Key"]

                if not s3_key.endswith(".json"):
                    continue

                temp_path = f"/tmp/{Path(s3_key).name}"
                self.s3.download_file(self.bucket_arn, s3_key, temp_path)

                with open(temp_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                vision_results = data.get("vision_extraction_result", [])
                if not vision_results:
                    continue

                metadata = vision_results[0].get("structure", {}).get("metadata", {})

                match = True
                if title and title.lower() not in metadata.get("title", "").lower():
                    match = False
                if country and country != metadata.get("country"):
                    match = False
                if regulation_type and regulation_type != metadata.get(
                    "regulation_type"
                ):
                    match = False

                if match:
                    matched_files.append(
                        {
                            "s3_key": s3_key,
                            "metadata": metadata,
                            "last_modified": obj["LastModified"].isoformat(),
                        }
                    )

            logger.info(f"✅ S3 검색 완료: {len(matched_files)}개 파일")
            return matched_files

        except Exception as e:
            logger.error(f"❌ S3 검색 실패: {e}")
            return []
