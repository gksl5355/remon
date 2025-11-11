"""
module: auth_api.py
description: 관리자 인증 API (로그인/로그아웃)
author: 조영우
created: 2025-11-10
updated: 2025-11-11
dependencies:
    - fastapi
    - app.services.auth_service
    - app.core.database
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])
service = AuthService()


@router.post("/login")
async def login(
    username: str,
    password: str,
    db: AsyncSession = Depends(get_db)
):
    """
    관리자 로그인을 처리한다.

    Args:
        username (str): 사용자명.
        password (str): 비밀번호.

    Returns:
        dict: 액세스 토큰 및 사용자 정보.

    Raises:
        HTTPException: 인증 실패 시 401.
    """
    logger.info(f"POST /auth/login - username={username}")
    result = await service.authenticate(username, password, db)
    
    if not result:
        logger.warning(f"Login failed for username={username}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return result


@router.post("/logout")
async def logout(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    관리자 로그아웃을 처리한다.

    Args:
        token (str): 액세스 토큰.

    Returns:
        dict: 로그아웃 성공 메시지.
    """
    logger.info(f"POST /auth/logout")
    await service.logout(token, db)
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_current_user(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    현재 로그인한 사용자 정보를 조회한다.

    Args:
        token (str): 액세스 토큰.

    Returns:
        dict: 사용자 정보.

    Raises:
        HTTPException: 토큰이 유효하지 않은 경우 401.
    """
    logger.info(f"GET /auth/me")
    user = await service.get_current_user(token, db)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return user
