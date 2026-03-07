# ============================================
# TorStream - Authentication Dependencies
# ============================================

from typing import Optional
from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.services.security import decode_token
from app.services.redis import redis_service
import logging

logger = logging.getLogger(__name__)
security_bearer = HTTPBearer(auto_error=False)


# ===== ADD THIS FUNCTION HERE =====
def get_client_ip(request: Request) -> str:
    """Get client IP address safely."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
# ==================================


async def get_token_from_request(request: Request) -> Optional[str]:
    """Extract JWT token from request (cookie or header)."""
    # Try cookie first (preferred for web)
    token = request.cookies.get("access_token")
    if token:
        return token
    
    # Try Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    
    return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current authenticated user."""
    token = await get_token_from_request(request)
    
    if not token:
        return None
    
    # Decode token
    payload = decode_token(token)
    if not payload:
        return None
    
    # Check token type
    if payload.get("type") != "access":
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    # Check session validity in Redis
    session_token = payload.get("session_token")
    if session_token and redis_service.is_available:
        session_key = f"session:{user_id}:{session_token}"
        is_valid = await redis_service.get_str(session_key)
        if not is_valid:
            return None
    
    # Get user from database
    try:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user and user.is_banned:
            logger.warning(f"Banned user attempted access: {user.username}")
            return None
        
        return user
        
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        return None


async def get_current_admin(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current admin user."""
    user = await get_current_user(request, db)
    
    if not user:
        return None
    
    if not user.is_admin and not user.is_superadmin:
        return None
    
    return user


async def get_current_superadmin(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current superadmin user."""
    user = await get_current_user(request, db)
    
    if not user:
        return None
    
    if not user.is_superadmin:
        return None
    
    return user


async def require_auth(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """Require authentication, raise 401 if not authenticated."""
    user = await get_current_user(request, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def require_admin(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """Require admin privileges."""
    user = await get_current_admin(request, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    
    return user


async def require_superadmin(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """Require superadmin privileges."""
    user = await get_current_superadmin(request, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required",
        )
    
    return user


async def optional_auth(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Optional authentication, returns None if not authenticated."""
    return await get_current_user(request, db)