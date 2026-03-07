# ============================================
# TorStream - Public Routes
# ============================================

from fastapi import APIRouter, Request, Depends, Query, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.video import Video, VideoAccessType
from app.models.user import User
from app.auth.dependencies import optional_auth, require_auth
from app.videos.service import video_service
from app.main import templates
from app.captcha.generator import captcha_generator
from datetime import datetime, timezone, timedelta
import logging
import uuid

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/browse", response_class=HTMLResponse)
async def browse(
    request: Request,
    page: int = Query(1, ge=1),
    category: str = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(optional_auth)
):
    """Public video browsing page."""
    limit = 20
    offset = (page - 1) * limit
    
    videos = await video_service.get_public_videos(db, limit=limit, offset=offset)
    
    return templates.TemplateResponse(
        "public/browse.html",
        {
            "request": request,
            "videos": videos,
            "page": page,
            "user": user
        }
    )


@router.get("/video/{video_id}", response_class=HTMLResponse)
async def video_detail(
    request: Request,
    video_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(optional_auth)
):
    """Video detail page - ENFORCES ACCESS CONTROL for both real and placeholder videos."""
    
    try:
        vid = uuid.UUID(video_id)
    except ValueError:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request},
            status_code=404
        )
    
    video = await video_service.get_video_by_id(db, vid)
    
    if not video or not video.is_active:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request},
            status_code=404
        )
    
    # ========== PLACEHOLDER VIDEOS ==========
    if video.is_placeholder:
        # Check access for placeholders like real videos
        can_access = await video_service.can_access_video(db, video, user)
        
        if not can_access:
            # Show locked page based on video type
            reason = "You don't have access to this video"
            if video.access_type == VideoAccessType.PREMIUM:
                reason = "This video requires a premium subscription"
            elif video.access_type == VideoAccessType.PPV:
                reason = f"This video requires a one-time purchase of ${video.ppv_price}"
            
            return templates.TemplateResponse(
                "public/video_locked.html",
                {
                    "request": request,
                    "video": video,
                    "user": user,
                    "reason": reason
                },
                status_code=403
            )
        else:
            # User has access - show placeholder page
            return templates.TemplateResponse(
                "public/placeholder.html",
                {
                    "request": request,
                    "video": video,
                    "user": user
                }
            )
    
    # ========== REAL VIDEOS ==========
    # ✅ CHECK ACCESS - Block unauthorized users BEFORE showing anything
    can_access = await video_service.can_access_video(db, video, user)
    
    if not can_access:
        # Show locked page based on video type
        reason = "You don't have access to this video"
        if video.access_type == VideoAccessType.PREMIUM:
            reason = "This video requires a premium subscription"
        elif video.access_type == VideoAccessType.PPV:
            reason = f"This video requires a one-time purchase of ${video.ppv_price}"
        
        return templates.TemplateResponse(
            "public/video_locked.html",
            {
                "request": request,
                "video": video,
                "user": user,
                "reason": reason
            },
            status_code=403
        )
    
    # ✅ User HAS access - show full video page
    has_purchased = False
    if user and video.access_type == VideoAccessType.PPV and not user.is_premium_active:
        has_purchased = await video_service.has_purchased(db, video.id, user.id)
    
    return templates.TemplateResponse(
        "public/video.html",
        {
            "request": request,
            "video": video,
            "can_access": can_access,
            "has_purchased": has_purchased,
            "user": user
        }
    )


@router.get("/preview/{video_id}")
async def serve_preview(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(optional_auth)
):
    """Serve preview clip - ONLY for FREE videos."""
    
    try:
        vid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    
    video = await video_service.get_video_by_id(db, vid)
    
    if not video or not video.preview_filename:
        raise HTTPException(status_code=404, detail="Not found")
    
    # ✅ Only FREE videos can show previews
    if video.access_type != VideoAccessType.FREE:
        raise HTTPException(status_code=403, detail="Access denied")
    
    response = Response()
    response.headers["X-Accel-Redirect"] = f"/previews/{video.preview_filename}"
    response.headers["Content-Type"] = "video/mp4"
    return response


@router.get("/thumbnail/{video_id}")
async def serve_thumbnail(
    video_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(optional_auth)
):
    """Serve thumbnail - accessible for browsing."""
    
    try:
        vid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    
    video = await video_service.get_video_by_id(db, vid)
    
    if not video or not video.thumbnail_filename:
        raise HTTPException(status_code=404, detail="Not found")
    
    # Thumbnails are visible to all for browsing
    response = Response()
    response.headers["X-Accel-Redirect"] = f"/previews/{video.thumbnail_filename}"
    response.headers["Content-Type"] = "image/jpeg"
    
    return response


# ==================== NEW ROUTE FOR PLACEHOLDER IMAGES ====================
@router.get("/placeholder-image/{video_id}")
async def serve_placeholder_image(
    video_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Serve custom placeholder image."""
    try:
        vid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    
    video = await video_service.get_video_by_id(db, vid)
    
    if not video or not video.placeholder_image:
        raise HTTPException(status_code=404, detail="Not found")
    
    response = Response()
    response.headers["X-Accel-Redirect"] = f"/previews/{video.placeholder_image}"
    response.headers["Content-Type"] = "image/jpeg"
    
    return response


@router.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(optional_auth)
):
    """Search videos."""
    videos = await video_service.search_videos(db, q)
    
    return templates.TemplateResponse(
        "public/search.html",
        {
            "request": request,
            "query": q,
            "videos": videos,
            "user": user
        }
    )


@router.get("/pricing", response_class=HTMLResponse)
async def pricing(
    request: Request,
    user: User = Depends(optional_auth)
):
    """Pricing page."""
    from app.config import settings
    
    return templates.TemplateResponse(
        "public/pricing.html",
        {
            "request": request,
            "monthly_price": settings.PREMIUM_MONTHLY_PRICE,
            "yearly_price": settings.PREMIUM_YEARLY_PRICE,
            "user": user
        }
    )


@router.get("/terms", response_class=HTMLResponse)
async def terms(
    request: Request,
    user: User = Depends(optional_auth)
):
    """Terms of Service page."""
    return templates.TemplateResponse(
        "public/terms.html",
        {
            "request": request,
            "user": user
        }
    )


@router.get("/contact", response_class=HTMLResponse)
async def contact_page(
    request: Request,
    user: User = Depends(optional_auth)
):
    """Contact page."""
    # Generate captcha
    captcha_data = await captcha_generator.generate()
    captcha_token, captcha_image = captcha_data if captcha_data else (None, None)
    
    return templates.TemplateResponse(
        "public/contact.html",
        {
            "request": request,
            "user": user,
            "captcha_token": captcha_token,
            "captcha_image": captcha_image,
            "error": None,
            "success": None
        }
    )


@router.post("/contact")
async def submit_contact(
    request: Request,
    name: str = Form(None),
    message: str = Form(..., min_length=5),
    captcha_token: str = Form(...),
    captcha_code: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """Submit contact form - REQUIRES LOGIN."""
    from app.models.admin import ContactMessage
    from app.auth.dependencies import get_client_ip
    
    # Generate new captcha in case of error
    captcha_data = await captcha_generator.generate()
    new_token, new_image = captcha_data if captcha_data else (None, None)
    
    # Verify captcha
    if not await captcha_generator.verify(captcha_token, captcha_code):
        return templates.TemplateResponse(
            "public/contact.html",
            {
                "request": request,
                "user": user,
                "error": "Invalid captcha. Please try again.",
                "captcha_token": new_token,
                "captcha_image": new_image
            },
            status_code=400
        )
    
    # Get IP for logging
    ip_address = get_client_ip(request)
    
    # Check rate limit by USER
    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
    existing = await db.execute(
        select(ContactMessage).where(
            ContactMessage.user_id == user.id,
            ContactMessage.created_at > three_days_ago
        )
    )
    
    if existing.scalar_one_or_none():
        return templates.TemplateResponse(
            "public/contact.html",
            {
                "request": request,
                "user": user,
                "error": "You can only submit one message per 3 days. Please try again later.",
                "captcha_token": new_token,
                "captcha_image": new_image
            },
            status_code=400
        )
    
    # Validate message length
    if len(message.strip()) < 10:
        return templates.TemplateResponse(
            "public/contact.html",
            {
                "request": request,
                "user": user,
                "error": "Message must be at least 10 characters long.",
                "captcha_token": new_token,
                "captcha_image": new_image
            },
            status_code=400
        )
    
    # Save message
    contact_msg = ContactMessage(
        user_id=user.id,
        ip_address=ip_address,
        name=name.strip() if name else None,
        message=message.strip(),
        is_read=False,
        is_replied=False
    )
    db.add(contact_msg)
    await db.commit()
    
    logger.info(f"Contact message received from user {user.id}: {contact_msg.id}")
    
    return templates.TemplateResponse(
        "public/contact.html",
        {
            "request": request,
            "user": user,
            "success": "Your message has been sent successfully. We'll review it shortly.",
            "captcha_token": new_token,
            "captcha_image": new_image
        }
    )


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(
    request: Request,
    user: User = Depends(optional_auth)
):
    """Privacy Policy page."""
    return templates.TemplateResponse(
        "public/privacy.html",
        {
            "request": request,
            "user": user
        }
    )