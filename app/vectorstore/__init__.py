"""VectorStore module - .env 자동 로드"""

from pathlib import Path

# .env 파일 로드
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                import os
                os.environ.setdefault(key, value)
