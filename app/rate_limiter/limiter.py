# ============================================
# TorStream - Rate Limiter
# ============================================

import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.redis import redis_service
from app.models.user import FailedLoginAttempt
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter with Redis primary and database fallback."""
    
    def __init__(self):
        self._local_cache = {}  # Fallback in-memory cache
    
    def _get_key(self, identifier: str, action: str) -> str:
        """Generate rate limit key."""
        return f"rate_limit:{action}:{identifier}"
    
    async def is_allowed(
        self,
        identifier: str,
        action: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, int]:
        """
        Check if request is allowed.
        Returns (allowed, remaining_requests).
        """
        key = self._get_key(identifier, action)
        
        # Try Redis first
        if redis_service.is_available:
            try:
                pipe = redis_service._pool.pipeline()
                pipe.incr(key)
                pipe.expire(key, window_seconds)
                results = await pipe.execute()
                current = results[0]
                
                if current == 1:
                    # First request, set expiration
                    await redis_service.expire(key, window_seconds)
                
                remaining = max(0, max_requests - current)
                allowed = current <= max_requests
                
                return allowed, remaining
                
            except Exception as e:
                logger.error(f"Redis rate limit error: {e}")
        
        # Fallback to in-memory cache
        return await self._memory_check(identifier, action, max_requests, window_seconds)
    
    async def _memory_check(
        self,
        identifier: str,
        action: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, int]:
        """In-memory rate limit fallback."""
        key = self._get_key(identifier, action)
        now = time.time()
        
        if key not in self._local_cache:
            self._local_cache[key] = []
        
        # Clean old entries
        cutoff = now - window_seconds
        self._local_cache[key] = [
            ts for ts in self._local_cache[key] if ts > cutoff
        ]
        
        # Add current request
        self._local_cache[key].append(now)
        
        current = len(self._local_cache[key])
        remaining = max(0, max_requests - current)
        allowed = current <= max_requests
        
        return allowed, remaining
    
    async def reset(self, identifier: str, action: str):
        """Reset rate limit for identifier."""
        key = self._get_key(identifier, action)
        
        if redis_service.is_available:
            await redis_service.delete(key)
        
        if key in self._local_cache:
            del self._local_cache[key]
    
    async def check_login_rate_limit(
        self,
        db: AsyncSession,
        ip_address: Optional[str],
        username: Optional[str]
    ) -> Tuple[bool, str]:
        """
        Check login rate limit using database for persistence.
        Returns (allowed, reason).
        """
        window = datetime.now(timezone.utc) - timedelta(
    seconds=settings.LOGIN_RATE_LIMIT_WINDOW
    )
        
        # Check IP-based limits
        if ip_address:
            ip_count = await db.scalar(
                select(func.count(FailedLoginAttempt.id))
                .where(
                    FailedLoginAttempt.ip_address == ip_address,
                    FailedLoginAttempt.attempted_at > window
                )
            )
            
            if ip_count and ip_count >= settings.LOGIN_RATE_LIMIT:
                logger.warning(f"Login rate limit exceeded for IP: {ip_address}")
                return False, "Too many failed attempts. Please try again later."
        
        # Check username-based limits
        if username:
            user_count = await db.scalar(
                select(func.count(FailedLoginAttempt.id))
                .where(
                    FailedLoginAttempt.username == username,
                    FailedLoginAttempt.attempted_at > window
                )
            )
            
            if user_count and user_count >= settings.LOGIN_RATE_LIMIT:
                logger.warning(f"Login rate limit exceeded for user: {username}")
                return False, "Too many failed attempts. Please try again later."
        
        return True, ""
    
    async def record_failed_login(
        self,
        db: AsyncSession,
        ip_address: Optional[str],
        username: Optional[str],
        reason: str
    ):
        """Record failed login attempt."""
        attempt = FailedLoginAttempt(
            ip_address=ip_address,
            username=username,
            reason=reason
        )
        db.add(attempt)
        await db.commit()
        
        logger.info(f"Failed login recorded: {username} from {ip_address} - {reason}")


# Global rate limiter instance
rate_limiter = RateLimiter()


async def get_rate_limiter() -> RateLimiter:
    """Get rate limiter instance."""
    return rate_limiter
