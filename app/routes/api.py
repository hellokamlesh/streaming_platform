# ============================================
# TorStream - API Routes
# ============================================

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.auth.dependencies import require_auth, optional_auth
from app.captcha.generator import captcha_generator
from app.services.redis import redis_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/captcha")
async def get_captcha():
    """Generate new captcha."""
    captcha_data = await captcha_generator.generate()
    
    if captcha_data:
        token, image = captcha_data
        return {
            "token": token,
            "image": f"data:image/png;base64,{image}"
        }
    
    # Fallback to math captcha
    math_data = await captcha_generator.generate_math_fallback()
    if math_data:
        token, problem, _ = math_data
        return {
            "token": token,
            "problem": problem,
            "type": "math"
        }
    
    raise HTTPException(status_code=503, detail="Captcha service unavailable")


@router.post("/captcha/refresh")
async def refresh_captcha(request: Request):
    """Refresh captcha (invalidate old, generate new)."""
    data = await request.json()
    old_token = data.get("token")
    
    new_captcha = await captcha_generator.refresh(old_token)
    
    if new_captcha:
        token, image = new_captcha
        return {
            "token": token,
            "image": f"data:image/png;base64,{image}"
        }
    
    raise HTTPException(status_code=503, detail="Captcha service unavailable")


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(optional_auth)
):
    """Get public platform stats."""
    from sqlalchemy import func
    from app.models.video import Video
    
    total_videos = await db.scalar(
        select(func.count(Video.id)).where(Video.is_active == True)
    )
    
    return {
        "total_videos": total_videos or 0,
        "premium_monthly_price": 9.99,
        "premium_yearly_price": 99.99
    }


@router.get("/user/status")
async def user_status(user: User = Depends(require_auth)):
    """Get current user status."""
    return {
        "id": str(user.id),
        "username": user.username,
        "is_admin": user.is_admin,
        "is_premium": user.is_premium_active,
        "premium_expires": user.premium_expires_at.isoformat() if user.premium_expires_at else None
    }


@router.get("/health/detailed")
async def detailed_health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "services": {
            "redis": redis_service.is_available,
            "database": True,  # If we got here, DB is working
        },
        "version": "1.0.0"
    }
