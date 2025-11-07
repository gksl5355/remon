"""
module: constants.py
description: 전역 상수, Enum, Path 정의
"""
from enum import Enum

class ErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
