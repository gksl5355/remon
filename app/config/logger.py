"""
module: logger.py
description: loguru 기반 로깅 설정
"""
from loguru import logger
import os

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
logger.add(f"{LOG_DIR}/app.log", rotation="1 week", encoding="utf-8", level="INFO")
