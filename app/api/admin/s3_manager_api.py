# app/api/admin/s3_manager_api.py

import os
from fastapi import APIRouter, UploadFile, Form, HTTPException, Query, Depends
from botocore.config import Config
import boto3
from typing import Optional
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from fastapi.responses import FileResponse

from app.utils.db import get_async_db, fetch_regul_data_by_title
from app.services.translation_service import TranslationService

router = APIRouter()

# ================================
# 환경 변수 로드
# ================================
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")

ACCESS_POINT_NAME = os.getenv("AWS_ACCESS_POINT_NAME")
AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID")

S3_BASE_PREFIX = os.getenv("S3_BASE_PREFIX")      # -> skala2
S3_APP_PREFIX = os.getenv("S3_APP_PREFIX")        # -> skala-2.4.17

# ================================
# Access Point ARN 생성
# ================================
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
# 파일 업로드
# ================================
@router.post("/upload")
async def upload_file(
    file: UploadFile,
    file_type: str = Form(...),  # "reg" | "report"
    country: str = Form(...),
):
    """
    S3 Access Point에 파일 업로드
    저장 경로 예:
    skala2/skala-2.4.17/remon/regulation/US/example.pdf
    """
    if file_type not in ("reg", "report"):
        raise HTTPException(status_code=400, detail="file_type must be reg or report")

    folder = "regulation" if file_type == "reg" else "AIreport"
    filename = file.filename

    s3_key = f"{S3_BASE_PREFIX}/{S3_APP_PREFIX}/remon/{folder}/{country}/{filename}"

    try:
        bytes_data = await file.read()

        s3_client.put_object(
            Bucket=ACCESS_POINT_ARN,
            Key=s3_key,
            Body=bytes_data,
            ContentType=file.content_type,
        )

        return {"status": "success", "key": s3_key}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ================================
# 파일 목록 조회
# ================================
@router.get("/list")
def list_files(
    file_type: Optional[str] = Query(None),  # "reg" | "report" | None
    country: Optional[str] = Query(None),    # US / RU / ID
):
    """
    조건별 파일 목록 조회 (프론트에서 바로 사용 가능하도록 데이터 정리)
    """
    prefix = f"{S3_BASE_PREFIX}/{S3_APP_PREFIX}/remon/"

    # 유형별 폴더
    if file_type == "reg":
        prefix += "regulation/"
    elif file_type == "report":
        prefix += "AIreport/"

    # 국가 폴더
    if country:
        prefix += f"{country}/"

    paginator = s3_client.get_paginator("list_objects_v2")
    results = []

    try:
        for page in paginator.paginate(Bucket=ACCESS_POINT_ARN, Prefix=prefix):
            for obj in page.get("Contents", []):

                key = obj["Key"]

                # 폴더 스킵
                if key.endswith("/"):
                    continue

                # 파일명
                name = key.split("/")[-1]

                # type
                file_type_detected = (
                    "reg" if "regulation" in key.lower() else "report"
                )

                # country
                parts = key.split("/")
                country_detected = parts[-2] if len(parts) >= 2 else ""

                # 응답 데이터 구조 일원화
                results.append({
                    "id": hash(key),
                    "name": name,
                    "country": country_detected,
                    "type": file_type_detected,
                    "s3_key": key,
                    "size": obj["Size"],
                    "date": obj["LastModified"].strftime("%Y-%m-%d")
                })

        return {"status": "success", "files": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ================================
# 파일 삭제
# ================================
@router.delete("/delete")
def delete_file(s3_key: str = Query(...)):
    """
    S3 파일 삭제
    """
    try:
        s3_client.delete_object(
            Bucket=ACCESS_POINT_ARN,
            Key=s3_key
        )
        return {"status": "success", "deleted": s3_key}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================================
# 파일 다운로드 (Presigned URL 생성)
# ================================
class DownloadURLRequest(BaseModel):
    key: str

@router.post("/download-url")
def generate_download_url(req: DownloadURLRequest):
    """
    주어진 s3_key에 대해 1시간 유효한 presigned URL 생성
    """
    try:
        url = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": ACCESS_POINT_ARN,
                "Key": req.key
            },
            ExpiresIn=3600
        )

        return {"status": "success", "url": url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================================
# Translation
# ================================
class TranslateGenerateRequest(BaseModel):
    s3_key: str
    target_lang: str = "ko"


@router.post("/translations/generate")
async def generate_translation_pdf(
    req: TranslateGenerateRequest,
    db: AsyncSession = Depends(get_async_db),
):
    # =========================
    # 1️⃣ 제목 추출
    # =========================
    filename = Path(req.s3_key).name
    title = Path(filename).stem

    # =========================
    # 2️⃣ DB 접근 (최소)
    # =========================
    regul_data = await fetch_regul_data_by_title(db, title)
    if regul_data is None:
        raise HTTPException(status_code=404, detail="Regulation not found")

    # DB 연결 즉시 종료
    await db.close()

    # =========================
    # 3️⃣ Markdown 원문 추출 (🔥 핵심)
    # =========================
    try:
        markdown_text = (
            regul_data["vision_extraction_result"][0]
            ["structure"]["markdown_content"]
        )
    except (KeyError, IndexError, TypeError):
        raise HTTPException(
            status_code=500,
            detail="Invalid regulation data structure (markdown_content not found)",
        )

    if not markdown_text.strip():
        raise HTTPException(
            status_code=500,
            detail="Regulation markdown content is empty",
        )

    # =========================
    # 4️⃣ 번역 + PDF 생성 (DB 완전 분리)
    # =========================
    service = TranslationService()

    result = await service.translate_markdown_to_pdf(
        markdown_text=markdown_text,
        target_lang=req.target_lang,
        title=f"{title} ({req.target_lang})",
    )

    # =========================
    # 5️⃣ PDF 응답
    # =========================
    pdf_path = result["pdf_path"]

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=Path(pdf_path).name,
    )


@router.get("/regulations/by-title")
async def get_regulation_by_title(
    title: str = Query(...),
    db: AsyncSession = Depends(get_async_db),
):
    """
    규제 원문 미리보기 조회 (번역 아님)
    """
    regul_data = await fetch_regul_data_by_title(db, title)

    if regul_data is None:
        raise HTTPException(status_code=404, detail="regul_data not found")

    return {
        "status": "success",
        "type": type(regul_data).__name__,
        "preview": regul_data[:1] if isinstance(regul_data, list) else regul_data,
    }
