from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.translation_service import TranslationService

router = APIRouter(prefix="/translations", tags=["Translations"])
service = TranslationService()


class TranslationRequest(BaseModel):
    regulation_version_id: int
    target_lang: str
    glossary_id: Optional[str] = None
    force: bool = False


class TranslationResponse(BaseModel):
    translation_id: Optional[int]
    regulation_version_id: int
    language: str
    status: str
    s3_key: Optional[str] = None
    presigned_url: Optional[str] = None
    error: Optional[str] = None


@router.post("", response_model=TranslationResponse, status_code=202)
async def trigger_translation(req: TranslationRequest, db: AsyncSession = Depends(get_db)):
    job = await service.trigger_translation(
        version_id=req.regulation_version_id,
        target_lang=req.target_lang,
        glossary_id=req.glossary_id,
        force=req.force,
        db=db,
    )
    return TranslationResponse(
        translation_id=job.translation_id,
        regulation_version_id=job.version_id,
        language=job.language,
        status=job.status,
        s3_key=job.s3_key,
        presigned_url=job.presigned_url,
        error=job.error,
    )


@router.get("/by-version/{version_id}", response_model=TranslationResponse)
async def get_translation_by_version(
    version_id: int,
    lang: str = Query(..., alias="lang"),
    db: AsyncSession = Depends(get_db),
):
    job = await service.get_translation(version_id=version_id, target_lang=lang, db=db)
    return TranslationResponse(
        translation_id=job.translation_id,
        regulation_version_id=job.version_id,
        language=job.language,
        status=job.status,
        s3_key=job.s3_key,
        presigned_url=job.presigned_url,
        error=job.error,
    )


@router.get("/{translation_id}/download")
async def download_translation(translation_id: int, db: AsyncSession = Depends(get_db)):
    job = await service.get_translation_by_id(translation_id, db)
    if job.status == "not_found":
        raise HTTPException(status_code=404, detail="Translation not found")
    if job.presigned_url:
        return {"url": job.presigned_url, "status": job.status}

    content = await service.get_translation_content(translation_id, db)
    if content is None:
        raise HTTPException(status_code=404, detail="Translation content not found")
    return PlainTextResponse(
        content,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="translation_{translation_id}.json"'
        },
    )
