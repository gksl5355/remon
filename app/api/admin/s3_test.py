import os
from dotenv import load_dotenv
import boto3
from botocore.config import Config

# --------------------------------------------------
# ENV LOAD
# --------------------------------------------------
load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")

AWS_ACCESS_POINT_NAME = os.getenv("AWS_ACCESS_POINT_NAME")   
AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID")           

S3_BASE_PREFIX = os.getenv("S3_BASE_PREFIX")    
S3_APP_PREFIX = os.getenv("S3_APP_PREFIX")       

# --------------------------------------------------
# Access Point ARN 생성
# --------------------------------------------------
ACCESS_POINT_ARN = (
    f"arn:aws:s3:{AWS_REGION}:{AWS_ACCOUNT_ID}:accesspoint/{AWS_ACCESS_POINT_NAME}"
)

# --------------------------------------------------
# S3 CLIENT (no endpoint_url)
# --------------------------------------------------
s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4")
)

# --------------------------------------------------
# LIST OBJECTS via Access Point ARN
# --------------------------------------------------
# def list_s3_files(prefix: str):
#     paginator = s3_client.get_paginator("list_objects_v2")
#     results = []

#     for page in paginator.paginate(
#         Bucket=ACCESS_POINT_ARN,
#         Prefix=prefix
#     ):
#         for obj in page.get("Contents", []):
#             results.append({
#                 "key": obj["Key"],
#                 "size": obj["Size"]
#             })

#     return results


def list_s3_pdf_files(prefix: str):
    paginator = s3_client.get_paginator("list_objects_v2")
    results = []

    for page in paginator.paginate(
        Bucket=ACCESS_POINT_ARN,
        Prefix=prefix
    ):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".pdf"):   # PDF 파일만 필터링
                results.append({
                    "key": key,
                    "size": obj["Size"]
                })

    return results


# --------------------------------------------------
# TEST
# --------------------------------------------------
if __name__ == "__main__":
    prefix = f"{S3_BASE_PREFIX}/{S3_APP_PREFIX}/remon"

    files = list_s3_pdf_files(prefix)

    print(f"\n📦 S3 PDF FILE LIST ({prefix})")
    for f in files:
        print(f"- {f['key']} ({f['size']} bytes)")

