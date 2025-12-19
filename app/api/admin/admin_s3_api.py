# app/api/admin/admin_s3_api.py

import os
import re
from pathlib import Path
from typing import Optional, Dict

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from fastapi import (
    APIRouter,
    UploadFile,
    Form,
    HTTPException,
    Query,
    Depends,
    BackgroundTasks,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel
import asyncio
import tempfile
from pathlib import Path
from sqlalchemy import text
from app.core.database import AsyncSessionLocal

from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.db import get_async_db, fetch_regul_data_by_title
from app.services.translation_service import TranslationService

# .env 파일 로드
ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(ROOT_DIR / ".env")

router = APIRouter()

# ==================================================
# ENV
# ==================================================
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")

# Keep env var names consistent with Kubernetes secrets (prefixed with AWS_)
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

# 파이프라인 상태를 DB에 기록하기 위한 설정
_pipeline_table_initialized = False


async def _ensure_pipeline_table(session) -> None:
    """pipeline_jobs 테이블이 없으면 생성 (간단한 상태 저장용)."""
    global _pipeline_table_initialized
    if _pipeline_table_initialized:
        return
    await session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS pipeline_jobs (
                s3_key TEXT PRIMARY KEY,
                status TEXT,
                error TEXT,
                updated_at TIMESTAMPTZ DEFAULT now()
            );
            """
        )
    )
    _pipeline_table_initialized = True


async def _set_job_status(s3_key: str, status: str, error: Optional[str] = None):
    async with AsyncSessionLocal() as session:
        await _ensure_pipeline_table(session)
        await session.execute(
            text(
                """
                INSERT INTO pipeline_jobs (s3_key, status, error, updated_at)
                VALUES (:s3_key, :status, :error, now())
                ON CONFLICT (s3_key) DO UPDATE
                SET status = EXCLUDED.status,
                    error = EXCLUDED.error,
                    updated_at = now();
                """
            ),
            {"s3_key": s3_key, "status": status, "error": error},
        )
        await session.commit()


async def _get_job_status(s3_key: str) -> Dict[str, str]:
    async with AsyncSessionLocal() as session:
        await _ensure_pipeline_table(session)
        res = await session.execute(
            text(
                "SELECT status, error, updated_at FROM pipeline_jobs WHERE s3_key = :s3_key"
            ),
            {"s3_key": s3_key},
        )
        row = res.fetchone()
        if row:
            return {"status": row.status, "error": row.error, "updated_at": str(row.updated_at)}
        return {"status": "unknown"}


# ==================================================
# PIPELINE TRIGGER
# ==================================================
class RunPipelineRequest(BaseModel):
    s3_key: str


async def _download_s3_to_tmp(s3_key: str) -> Path:
    """S3 객체를 임시 파일로 다운로드 후 경로 반환."""
    tmp_dir = Path(tempfile.gettempdir())
    local_path = tmp_dir / Path(s3_key).name
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, s3_client.download_file, ACCESS_POINT_ARN, s3_key, str(local_path))
    return local_path


async def _run_pipeline_worker(s3_key: str):
    """S3 키를 받아 파이프라인을 비동기로 실행."""
    try:
        from app.ai_pipeline.graph import build_graph

        # 1) S3 → 로컬 임시 저장
        local_pdf = await _download_s3_to_tmp(s3_key)

        # 2) 파이프라인 초기 상태 구성
        initial_state = {
            "preprocess_request": {
                "pdf_paths": [str(local_pdf)],
                "use_vision_pipeline": True,
                "enable_change_detection": True,
            },
            "change_context": {},
            "mapping_filters": {},
            "validation_retry_count": 0,
        }

        app = build_graph()
        await app.ainvoke(initial_state, config={"configurable": {}})
        logger.info("✅ pipeline completed for s3_key=%s", s3_key)
        await _set_job_status(s3_key, "done")
    except Exception as exc:
        logger.error("❌ pipeline failed for s3_key=%s, error=%s", s3_key, exc, exc_info=True)
        await _set_job_status(s3_key, "failed", str(exc))


@router.post("/run-pipeline")
async def run_pipeline_from_s3(req: RunPipelineRequest, background_tasks: BackgroundTasks):
    """
    S3 키로 업로드된 규제 PDF를 즉시 AI 파이프라인에 태우는 엔드포인트.
    응답은 바로 반환되고, 백그라운드에서 처리됩니다.
    """
    await _set_job_status(req.s3_key, "running")
    background_tasks.add_task(_run_pipeline_worker, req.s3_key)
    return {"status": "accepted", "s3_key": req.s3_key}


@router.get("/pipeline-status")
async def pipeline_status_check(s3_key: str):
    """
    파이프라인 상태 확인 (DB 기반).
    """
    return await _get_job_status(s3_key)

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
    key: Optional[str] = None
    s3_key: Optional[str] = None


@router.post("/download-url")
def generate_download_url(
    req: DownloadURLRequest,
    key: Optional[str] = Query(None),
    s3_key: Optional[str] = Query(None),
):
    selected = key or s3_key or req.key or req.s3_key
    if not selected:
        raise HTTPException(status_code=422, detail="key (or s3_key) is required")
    return {
        "status": "success",
        "url": generate_presigned_download_url(selected),
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
