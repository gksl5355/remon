"""
module: file_utils.py
description: 파일 처리 유틸리티.
"""
import os
def ensure_dir(path: str):
    """디렉토리가 없으면 생성."""
    if not os.path.exists(path): os.makedirs(path)
