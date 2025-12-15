# app/api/admin/admin_s3_api.py

import os
import re
from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from fastapi import APIRouter, UploadFile, Form, HTTPException, Query, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.db import get_async_db, fetch_regul_data_by_title
from app.services.translation_service import TranslationService


router = APIRouter()

# ==================================================
# ENV
# ==================================================
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")

ACCESS_POINT_NAME = os.getenv("AWS_ACCESS_POINT_NAME")
AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID")

S3_BASE_PREFIX = os.getenv("S3_BASE_PREFIX")    # skala2
S3_APP_PREFIX = os.getenv("S3_APP_PREFIX")      # skala-2.4.17

if not all([AWS_REGION, AWS_ACCOUNT_ID, ACCESS_POINT_NAME]):
    raise RuntimeError("AWS S3 Access Point environment variables are not set")

ACCESS_POINT_ARN = (
    f"arn:aws:s3:{AWS_REGION}:{AWS_ACCOUNT_ID}:accesspoint/{ACCESS_POINT_NAME}"
)

# ==================================================
# boto3 client
# ==================================================
s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
)

# ==================================================
# S3 HELPER FUNCTIONS
# ==================================================
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

# ==================================================
# UTIL
# ==================================================
def normalize_title(title: str) -> str:
    """
    S3 key용 canonical title
    """
    title = title.lower().strip()
    title = re.sub(r"[()]", "", title)
    title = re.sub(r"[^a-z0-9\s\-]", "", title)
    title = re.sub(r"\s+", "-", title)
    return title

# ==================================================
# FILE UPLOAD
# ==================================================
@router.post("/upload")
async def upload_file(
    file: UploadFile,
    file_type: str = Form(...),  # reg | report
    country: str = Form(...),
):
    if file_type not in ("reg", "report"):
        raise HTTPException(status_code=400, detail="file_type must be reg or report")

    folder = "regulation" if file_type == "reg" else "AIreport"
    filename = file.filename

    s3_key = f"{S3_BASE_PREFIX}/{S3_APP_PREFIX}/remon/{folder}/{country}/{filename}"

    try:
        data = await file.read()
        s3_client.put_object(
            Bucket=ACCESS_POINT_ARN,
            Key=s3_key,
            Body=data,
            ContentType=file.content_type,
        )
        return {"status": "success", "s3_key": s3_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================================================
# FILE LIST
# ==================================================
@router.get("/list")
def list_files(
    file_type: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
):
    prefix = f"{S3_BASE_PREFIX}/{S3_APP_PREFIX}/remon/"

    if file_type == "reg":
        prefix += "regulation/"
    elif file_type == "report":
        prefix += "AIreport/"

    if country:
        prefix += f"{country}/"

    paginator = s3_client.get_paginator("list_objects_v2")
    results = []

    for page in paginator.paginate(Bucket=ACCESS_POINT_ARN, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue

            parts = key.split("/")
            results.append({
                "id": hash(key),
                "name": parts[-1],
                "country": parts[-2] if len(parts) > 2 else "",
                "type": "reg" if "regulation" in key else "report",
                "s3_key": key,
                "size": obj["Size"],
                "date": obj["LastModified"].strftime("%Y-%m-%d"),
            })

    return {"status": "success", "files": results}

# ==================================================
# FILE DELETE
# ==================================================
@router.delete("/delete")
def delete_file(s3_key: str = Query(...)):
    try:
        s3_client.delete_object(
            Bucket=ACCESS_POINT_ARN,
            Key=s3_key,
        )
        return {"status": "success", "deleted": s3_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================================================
# PRESIGNED DOWNLOAD
# ==================================================
class DownloadURLRequest(BaseModel):
    key: str


@router.post("/download-url")
def generate_download_url(req: DownloadURLRequest):
    return {
        "status": "success",
        "url": generate_presigned_download_url(req.key),
    }

# ==================================================
# TRANSLATION
# ==================================================
class TranslateGenerateRequest(BaseModel):
    s3_key: str
    target_lang: str = "ko"


@router.post("/translations/generate")
async def generate_translation_pdf(
    req: TranslateGenerateRequest,
    db: AsyncSession = Depends(get_async_db),
):
    raw_title = Path(req.s3_key).stem
    lang = req.target_lang

    normalized = normalize_title(raw_title)
    pdf_filename = f"{normalized}__{lang}.pdf"

    # 🔥 변경된 저장 위치
    s3_key = (
        f"{S3_BASE_PREFIX}/{S3_APP_PREFIX}/remon/"
        f"translation/{pdf_filename}"
    )

    # 이미 존재
    if s3_object_exists(s3_key):
        return {
            "status": "exists",
            "s3_key": s3_key,
            "download_url": generate_presigned_download_url(s3_key),
        }

    regul_data = await fetch_regul_data_by_title(db, raw_title)
    if regul_data is None:
        raise HTTPException(status_code=404, detail="Regulation not found")

    try:
        markdown_text = (
            regul_data["vision_extraction_result"][0]
            ["structure"]["markdown_content"]
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Invalid regulation data structure")

    if not markdown_text.strip():
        raise HTTPException(status_code=500, detail="Regulation markdown content is empty")

    service = TranslationService()
    result = await service.translate_markdown_to_pdf(
        markdown_text=markdown_text,
        target_lang=lang,
        title=raw_title,
    )

    upload_pdf_to_s3(result["pdf_path"], s3_key)

    return {
        "status": "created",
        "s3_key": s3_key,
        "download_url": generate_presigned_download_url(s3_key),
    }

# ==================================================
# REGULATION PREVIEW
# ==================================================
@router.get("/regulations/by-title")
async def get_regulation_by_title(
    title: str = Query(...),
    db: AsyncSession = Depends(get_async_db),
):
    regul_data = await fetch_regul_data_by_title(db, title)
    if regul_data is None:
        raise HTTPException(status_code=404, detail="regul_data not found")

    return {
        "status": "success",
        "type": type(regul_data).__name__,
        "preview": regul_data[:1] if isinstance(regul_data, list) else regul_data,
    }
