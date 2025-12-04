"""Small helper to read an object from S3 (Access Point) using .env values."""
import argparse
import os

import boto3
from dotenv import load_dotenv


def build_key(base_prefix: str, app_prefix: str, path: str) -> str:
    # Always join with forward slashes; strip leading slashes to avoid double separators.
    return f"{base_prefix.rstrip('/')}/{app_prefix.strip('/')}/{path.lstrip('/')}"


def read_object(bucket_arn: str, key: str, region: str | None = None) -> str:
    s3 = boto3.client("s3", region_name=region)
    resp = s3.get_object(Bucket=bucket_arn, Key=key)
    return resp["Body"].read().decode("utf-8")


def main() -> None:
    load_dotenv()

    bucket_arn = os.environ["AWS_S3_ACCESS_POINT_ARN"]
    base_prefix = os.environ.get("S3_BASE_PREFIX", "skala2")
    app_prefix = os.environ.get("S3_APP_PREFIX", "skala-2.4.17")
    region = os.environ.get("AWS_DEFAULT_REGION")

    parser = argparse.ArgumentParser(description="Read a file from S3 Access Point")
    parser.add_argument(
        "path",
        nargs="?",
        default="hello.txt",
        help="path under skala2/skala-2.4.17 (default: hello.txt)",
    )
    args = parser.parse_args()

    key = build_key(base_prefix, app_prefix, args.path)
    content = read_object(bucket_arn, key, region)

    print(f"Bucket (Access Point ARN): {bucket_arn}")
    print(f"Key: {key}")
    print("---- content ----")
    print(content, end="" if content.endswith("\n") else "\n")


if __name__ == "__main__":
    main()
