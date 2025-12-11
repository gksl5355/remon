"""
module: redis_utils.py
description: Redis 캐시 헬퍼
"""
import redis

def get_redis_client(url: str = "redis://localhost:6379/0"):
    return redis.Redis.from_url(url)
