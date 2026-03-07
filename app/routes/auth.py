# ============================================
# TorStream - Authentication Routes
# ============================================

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User, UserSession, FailedLoginAttempt
from app.auth.dependencies import get_current_user, require_auth
from app.services.security import (
    verify_password, hash_password, create_access_token,
    create_refresh_token, decode_token, generate_session_token,
    hash_user_agent
)
from app.services.redis import redis_service
from app.rate_limiter.limiter import rate_limiter
from app.captcha.generator import captcha_generator
from app.config import settings
from app.main import templates
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def get_client_ip(request: Request) -> str:
    """Get client IP address safely."""
    # For Tor, we don't want to deanonymize
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page."""
    if not settings.REGISTRATION_ENABLED:
        return templates.TemplateResponse(
            "errors/maintenance.html",
            {"request": request, "message": "Registration is currently disabled"}
        )
    
    # Generate captcha
    captcha_data = await captcha_generator.generate()
    if captcha_data:
        captcha_token, captcha_image = captcha_data
    else:
        # Fallback to math captcha
        math_data = await captcha_generator.generate_math_fallback()
        if math_data:
            captcha_token, captcha_image, _ = math_data
        else:
            captcha_token, captcha_image = None, None
    
    return templates.TemplateResponse(
        "auth/register.html",
        {
            "request": request,
            "captcha_token": captcha_token,
            "captcha_image": captcha_image,
            "registration_enabled": settings.REGISTRATION_ENABLED
        }
    )


@router.post("/register")
async def register(
    request: Request,
    username: str = Form(..., min_length=3, max_length=32),
    password: str = Form(..., min_length=8),
    captcha_token: str = Form(...),
    captcha_code: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Handle registration with error display in UI."""
    if not settings.REGISTRATION_ENABLED:
        raise HTTPException(status_code=403, detail="Registration is disabled")
    
    # Validate username (alphabetic only as per requirements)
    if not username.isalpha():
        # Generate new captcha for retry
        captcha_data = await captcha_generator.generate()
        new_token, new_image = captcha_data if captcha_data else (None, None)
        
        return templates.TemplateResponse(
            "auth/register.html",
            {
                "request": request,
                "error": "Username must contain only letters",
                "username": username,
                "captcha_token": new_token,
                "captcha_image": new_image,
                "registration_enabled": settings.REGISTRATION_ENABLED
            },
            status_code=400
        )
    
    # Verify captcha
    if not await captcha_generator.verify(captcha_token, captcha_code):
        # Generate new captcha for retry
        captcha_data = await captcha_generator.generate()
        new_token, new_image = captcha_data if captcha_data else (None, None)
        
        return templates.TemplateResponse(
            "auth/register.html",
            {
                "request": request,
                "error": "Invalid captcha. Please try again.",
                "username": username,
                "captcha_token": new_token,
                "captcha_image": new_image,
                "registration_enabled": settings.REGISTRATION_ENABLED
            },
            status_code=400
        )
    
    # Check if username exists
    existing = await db.execute(
        select(User).where(User.username == username)
    )
    if existing.scalar_one_or_none():
        # Generate new captcha for retry
        captcha_data = await captcha_generator.generate()
        new_token, new_image = captcha_data if captcha_data else (None, None)
        
        return templates.TemplateResponse(
            "auth/register.html",
            {
                "request": request,
                "error": "Username already taken",
                "username": username,
                "captcha_token": new_token,
                "captcha_image": new_image,
                "registration_enabled": settings.REGISTRATION_ENABLED
            },
            status_code=400
        )
    
    # Create user (only reaches here if all validations pass)
    user = User(
        username=username,
        password_hash=hash_password(password),
        is_admin=False,
        is_superadmin=False,
        is_premium=False
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    logger.info(f"New user registered: {username}")
    
    # Redirect to login
    return RedirectResponse(url="/auth/login?registered=true", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, registered: bool = False, error: str = None):
    """Login page."""
    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "registered": registered,
            "error": error
        }
    )


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Handle login."""
    ip_address = get_client_ip(request)
    
    # Check rate limit
    allowed, reason = await rate_limiter.check_login_rate_limit(db, ip_address, username)
    if not allowed:
        # Return styled HTML error instead of raw JSON
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": reason,
                "registered": False
            },
            status_code=429
        )
    
    # Find user
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    
    # Verify credentials
    if not user or not verify_password(password, user.password_hash):
        # Record failed attempt
        await rate_limiter.record_failed_login(
            db, ip_address, username,
            "invalid_credentials" if user else "user_not_found"
        )
        
        logger.warning(f"Failed login attempt: {username} from {ip_address}")
        
        # Return generic error
        if request.headers.get("accept", "").startswith("application/json"):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        return RedirectResponse(
            url="/auth/login?error=invalid",
            status_code=303
        )
    
    # Check if banned
    if user.is_banned:
        await rate_limiter.record_failed_login(db, ip_address, username, "user_banned")
        raise HTTPException(status_code=403, detail="Account banned")
    
    # Generate tokens
    session_token = generate_session_token()
    access_token = create_access_token({
        "sub": str(user.id),
        "username": user.username,
        "is_admin": user.is_admin,
        "session_token": session_token
    })
    refresh_token = create_refresh_token({"sub": str(user.id)})
    
    # Create session record
    user_agent = request.headers.get("user-agent", "")
    session = UserSession(
        user_id=user.id,
        session_token=session_token,
        ip_address=ip_address,
        user_agent_hash=hash_user_agent(user_agent),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        is_valid=True
    )
    db.add(session)
    
    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    
    # Store session in Redis
    if redis_service.is_available:
        await redis_service.set(
            f"session:{user.id}:{session_token}",
            "1",
            expire=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
        )
    
    logger.info(f"User logged in: {username} from {ip_address}")
    
    # Set cookies and redirect
    response = RedirectResponse(url="/user/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        **settings.cookie_settings
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
    )
    
    return response


@router.post("/logout")
async def logout(
    request: Request,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Handle logout."""
    # Invalidate session in Redis
    token = await get_token_from_request(request)
    if token:
        payload = decode_token(token)
        if payload:
            session_token = payload.get("session_token")
            if session_token and redis_service.is_available:
                await redis_service.delete(f"session:{user.id}:{session_token}")
    
    logger.info(f"User logged out: {user.username}")
    
    # Clear cookies
    response = RedirectResponse(url="/home", status_code=303)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    
    return response


@router.get("/refresh")
async def refresh_token(request: Request):
    """Refresh access token."""
    refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Generate new access token
    new_token = create_access_token({"sub": user_id})
    
    response = JSONResponse({"status": "ok"})
    response.set_cookie(
        key="access_token",
        value=new_token,
        **settings.cookie_settings
    )
    
    return response


async def get_token_from_request(request: Request) -> str:
    """Extract token from request."""
    token = request.cookies.get("access_token")
    if token:
        return token
    
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    
    return ""
