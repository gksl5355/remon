# app/utils/text_utils.py

import re

def normalize_title(title: str) -> str:
    """
    S3 key용 canonical title 생성
    """
    title = title.lower().strip()
    title = re.sub(r"[()]", "", title)
    title = re.sub(r"[^a-z0-9\s\-]", "", title)
    title = re.sub(r"\s+", "-", title)
    return title
