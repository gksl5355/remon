# app/services/s3_directory_service.py

import os
import boto3
from botocore.config import Config
from typing import List, Dict, Optional

from dotenv import load_dotenv
load_dotenv()

# ================================
# ENV
# ================================
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")

ACCESS_POINT_NAME = os.getenv("AWS_ACCESS_POINT_NAME")
AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID")

S3_BASE_PREFIX = os.getenv("S3_BASE_PREFIX")   # skala2
S3_APP_PREFIX = os.getenv("S3_APP_PREFIX")     # skala-2.4.17

ACCESS_POINT_ARN = (
    f"arn:aws:s3:{AWS_REGION}:{AWS_ACCOUNT_ID}:accesspoint/{ACCESS_POINT_NAME}"
)

# ================================
# boto3 client
# ================================
s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
)


# ================================
# Core Function
# ================================
def list_s3_files_by_directory(
    directory: str,
    recursive: bool = True,
) -> List[Dict]:

    prefix = f"{S3_BASE_PREFIX}/{S3_APP_PREFIX}/{directory}".rstrip("/") + "/"

    paginator = s3_client.get_paginator("list_objects_v2")
    results: List[Dict] = []

    paginate_kwargs = {
        "Bucket": ACCESS_POINT_ARN,
        "Prefix": prefix,
    }

    # 🔥 recursive 아닐 때만 Delimiter 지정
    if not recursive:
        paginate_kwargs["Delimiter"] = "/"

    for page in paginator.paginate(**paginate_kwargs):
        for obj in page.get("Contents", []):
            key = obj["Key"]

            if key.endswith("/"):
                continue

            results.append({
                "key": key,
                "filename": key.split("/")[-1],
                "size": obj["Size"],
                "last_modified": obj["LastModified"],
            })

    return results


if __name__ == "__main__":
    files = list_s3_files_by_directory(
        directory="remon/",  # 🔥 보고 싶은 경로
        recursive=True,
    )

    print(f"📂 Found {len(files)} files")
    for f in files:
        print(f["key"])