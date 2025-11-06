"""
module: constants.py
description: 전역 상수 및 Enum 정의.
"""
from enum import Enum
class Stage(str, Enum):
    COLLECT = "collect"
    REFINE = "refine"
    MAPPING = "mapping"
    REPORT = "report"
    ADMIN = "admin"
