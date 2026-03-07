# ============================================
# TorStream - Redis Service
# ============================================

import json
import pickle
from typing import Optional, Any, Union
import redis.asyncio as redis
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class RedisService:
    """Redis service with connection pooling and error handling."""
    
    def __init__(self):
        self._pool: Optional[redis.Redis] = None
        self._available = False
    
    async def connect(self):
        """Initialize Redis connection."""
        try:
            self._pool = redis.from_url(
                settings.REDIS_URL,
                decode_responses=False,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
            )
            # Test connection
            await self._pool.ping()
            self._available = True
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self._available = False
            self._pool = None
    
    async def disconnect(self):
        """Close Redis connection."""
        if self._pool:
            await self._pool.close()
            self._available = False
            logger.info("Redis connection closed")
    
    @property
    def is_available(self) -> bool:
        """Check if Redis is available."""
        return self._available and self._pool is not None
    
    async def get(self, key: str) -> Optional[bytes]:
        """Get value by key."""
        if not self.is_available:
            return None
        try:
            return await self._pool.get(key)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def get_str(self, key: str) -> Optional[str]:
        """Get string value by key."""
        value = await self.get(key)
        return value.decode('utf-8') if value else None
    
    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value by key."""
        value = await self.get_str(key)
        return json.loads(value) if value else None
    
    async def set(
        self,
        key: str,
        value: Union[str, bytes],
        expire: Optional[int] = None
    ) -> bool:
        """Set value with optional expiration (seconds)."""
        if not self.is_available:
            return False
        try:
            if isinstance(value, str):
                value = value.encode('utf-8')
            await self._pool.set(key, value, ex=expire)
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def set_json(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        """Set JSON value with optional expiration."""
        return await self.set(key, json.dumps(value), expire)
    
    async def delete(self, key: str) -> bool:
        """Delete key."""
        if not self.is_available:
            return False
        try:
            await self._pool.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self.is_available:
            return False
        try:
            return await self._pool.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter."""
        if not self.is_available:
            return None
        try:
            return await self._pool.incr(key, amount)
        except Exception as e:
            logger.error(f"Redis increment error: {e}")
            return None
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key."""
        if not self.is_available:
            return False
        try:
            return await self._pool.expire(key, seconds)
        except Exception as e:
            logger.error(f"Redis expire error: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """Get time to live for key."""
        if not self.is_available:
            return -2
        try:
            return await self._pool.ttl(key)
        except Exception as e:
            logger.error(f"Redis ttl error: {e}")
            return -2


# Global Redis instance
redis_service = RedisService()


async def get_redis() -> RedisService:
    """Get Redis service instance."""
    return redis_service
