"""
module: logger.py
description: 공통 로깅 설정.
"""
import logging, os
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s - %(message)s")
console = logging.StreamHandler(); console.setFormatter(formatter)
file_handler = logging.FileHandler(f"{LOG_DIR}/app.log", encoding="utf-8")
file_handler.setFormatter(formatter)
logger = logging.getLogger("app"); logger.setLevel(logging.INFO)
logger.addHandler(console); logger.addHandler(file_handler)
