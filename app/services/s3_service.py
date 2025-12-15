# app/services/s3_service.py

import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")

ACCESS_POINT_NAME = os.getenv("AWS_ACCESS_POINT_NAME")
AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID")

S3_BASE_PREFIX = os.getenv("S3_BASE_PREFIX")
S3_APP_PREFIX = os.getenv("S3_APP_PREFIX")

ACCESS_POINT_ARN = (
    f"arn:aws:s3:{AWS_REGION}:{AWS_ACCOUNT_ID}:accesspoint/{ACCESS_POINT_NAME}"
)

s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
)


def upload_pdf_to_s3(local_path: str, s3_key: str):
    with open(local_path, "rb") as f:
        s3_client.put_object(
            Bucket=ACCESS_POINT_ARN,
            Key=s3_key,
            Body=f,
            ContentType="application/pdf",
        )


def s3_object_exists(key: str) -> bool:
    try:
        s3_client.head_object(
            Bucket=ACCESS_POINT_ARN,
            Key=key,
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def generate_presigned_download_url(key: str, expires: int = 3600) -> str:
    return s3_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": ACCESS_POINT_ARN,
            "Key": key,
        },
        ExpiresIn=expires,
    )
