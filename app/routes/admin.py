# ============================================
# TorStream - Admin Routes
# ============================================

import uuid
from fastapi import APIRouter, Request, Depends, Form, Query, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import joinedload
from app.database import get_db
from app.models.user import User
from app.models.video import Video
from app.models.payment import Purchase, Invoice
from app.auth.dependencies import require_admin, require_superadmin
from app.admin.service import admin_service
from app.videos.service import video_service
from app.payments.service import payment_service
from app.main import templates
from app.config import settings
from datetime import datetime, timezone
from pathlib import Path
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter()


def get_client_ip(request: Request) -> str:
    """Get client IP address."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin dashboard."""
    stats = await admin_service.get_statistics(db)
    
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "user": user,
            "stats": stats
        }
    )


@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    page: int = Query(1, ge=1),
    search: str = Query(None),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """User management page."""
    limit = 50
    offset = (page - 1) * limit
    
    users = await admin_service.get_users(db, limit=limit, offset=offset, search=search)
    
    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "page": page,
            "search": search
        }
    )


@router.post("/users/{user_id}/ban")
async def ban_user(
    request: Request,
    user_id: str,
    reason: str = Form(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Ban a user."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")
    
    target_user = await admin_service.get_user_by_id(db, uid)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    ip = get_client_ip(request)
    success = await admin_service.ban_user(db, admin, target_user, reason, ip)
    
    if not success:
        raise HTTPException(status_code=400, detail="Cannot ban user")
    
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/unban")
async def unban_user(
    request: Request,
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Unban a user."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")
    
    target_user = await admin_service.get_user_by_id(db, uid)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    ip = get_client_ip(request)
    await admin_service.unban_user(db, admin, target_user, ip)
    
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/grant-premium")
async def grant_premium(
    request: Request,
    user_id: str,
    days: int = Form(30),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Grant premium to user."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")
    
    target_user = await admin_service.get_user_by_id(db, uid)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    ip = get_client_ip(request)
    await admin_service.grant_premium(db, admin, target_user, days, ip)
    
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/revoke-premium")
async def revoke_premium(
    request: Request,
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Revoke premium from user."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")
    
    target_user = await admin_service.get_user_by_id(db, uid)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    ip = get_client_ip(request)
    await admin_service.revoke_premium(db, admin, target_user, ip)
    
    return RedirectResponse(url="/admin/users", status_code=303)


@router.get("/videos", response_class=HTMLResponse)
async def admin_videos(
    request: Request,
    page: int = Query(1, ge=1),
    filter: str = Query("all"),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Video management page with filters."""
    limit = 50
    offset = (page - 1) * limit
    
    # Use new filtered method
    videos = await video_service.get_videos_filtered(
        db,
        filter_type=filter,
        limit=limit,
        offset=offset
    )
    
    return templates.TemplateResponse(
        "admin/videos.html",
        {
            "request": request,
            "user": user,
            "videos": videos,
            "page": page,
            "filter": filter
        }
    )


@router.post("/videos/{video_id}/toggle")
async def toggle_video(
    request: Request,
    video_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Toggle video active status."""
    try:
        vid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video = await video_service.get_video_by_id(db, vid)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    ip = get_client_ip(request)
    await admin_service.toggle_video_active(db, admin, video, ip)
    
    return RedirectResponse(url="/admin/videos", status_code=303)


@router.post("/videos/{video_id}/delete")
async def delete_video(
    request: Request,
    video_id: str,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db)
):
    """Delete video (superadmin only)."""
    try:
        vid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video = await video_service.get_video_by_id(db, vid)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    ip = get_client_ip(request)
    success = await admin_service.delete_video(db, admin, video, ip)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete video")
    
    return RedirectResponse(url="/admin/videos", status_code=303)


# ============================================
# THUMBNAIL CONTROL ENDPOINTS (ADDITIVE)
# ============================================

@router.post("/videos/{video_id}/blur")
async def update_video_blur(
    request: Request,
    video_id: str,
    blur_level: str = Form("none"),
    blur_until_date: str = Form(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update video blur settings."""
    try:
        vid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video = await video_service.get_video_by_id(db, vid)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Validate blur level
    if blur_level not in ["none", "light", "heavy", "full"]:
        raise HTTPException(status_code=400, detail="Invalid blur level")
    
    # Parse blur_until_date if provided
    blur_date = None
    if blur_until_date:
        try:
            blur_date = datetime.fromisoformat(blur_until_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    
    await video_service.update_video(
        db,
        video,
        blur_level=blur_level,
        blur_until_date=blur_date
    )
    
    logger.info(f"Video blur updated by {admin.username}: {vid} -> {blur_level}")
    
    return RedirectResponse(url=f"/admin/videos", status_code=303)


@router.post("/videos/{video_id}/placeholder")
async def update_video_placeholder(
    request: Request,
    video_id: str,
    is_placeholder: str = Form("false"),
    placeholder_message: str = Form("Coming Soon"),
    fake_duration_seconds: str = Form(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update video placeholder settings."""
    try:
        vid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video = await video_service.get_video_by_id(db, vid)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    is_ph = is_placeholder.lower() == "true"
    
    # Parse fake duration
    fake_duration = None
    if fake_duration_seconds and fake_duration_seconds.strip():
        try:
            fake_duration = int(fake_duration_seconds)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid duration format")
    
    await video_service.update_video(
        db,
        video,
        is_placeholder=is_ph,
        placeholder_message=placeholder_message or "Coming Soon",
        fake_duration_seconds=fake_duration
    )
    
    logger.info(f"Video placeholder updated by {admin.username}: {vid} -> {is_ph}")
    
    return RedirectResponse(url=f"/admin/videos", status_code=303)


@router.post("/videos/{video_id}/blur-image")
async def upload_blur_image(
    request: Request,
    video_id: str,
    blur_image: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Upload custom blur image for video."""
    try:
        vid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video = await video_service.get_video_by_id(db, vid)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Validate image file
    if not blur_image.content_type or not blur_image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Save custom blur image
    preview_path = Path(settings.PREVIEW_STORAGE_PATH)
    blur_filename = f"blur_{video.id}_{blur_image.filename}"
    blur_filepath = preview_path / blur_filename
    
    try:
        with open(blur_filepath, "wb") as f:
            while chunk := await blur_image.read(8192):
                f.write(chunk)
    except Exception as e:
        logger.error(f"Error saving blur image: {e}")
        raise HTTPException(status_code=500, detail="Error saving image")
    
    # Update video with blur image
    await video_service.update_video(db, video, custom_blur_image=blur_filename)
    
    logger.info(f"Custom blur image uploaded by {admin.username}: {vid}")
    
    return RedirectResponse(url=f"/admin/videos", status_code=303)


@router.post("/videos/{video_id}/placeholder-image")
async def upload_placeholder_image(
    request: Request,
    video_id: str,
    placeholder_image: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Upload custom placeholder image for video."""
    try:
        vid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video = await video_service.get_video_by_id(db, vid)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Validate image file
    if not placeholder_image.content_type or not placeholder_image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Save placeholder image
    preview_path = Path(settings.PREVIEW_STORAGE_PATH)
    placeholder_filename = f"placeholder_{video.id}_{placeholder_image.filename}"
    placeholder_filepath = preview_path / placeholder_filename
    
    try:
        with open(placeholder_filepath, "wb") as f:
            while chunk := await placeholder_image.read(8192):
                f.write(chunk)
    except Exception as e:
        logger.error(f"Error saving placeholder image: {e}")
        raise HTTPException(status_code=500, detail="Error saving image")
    
    # Update video with placeholder image
    await video_service.update_video(db, video, placeholder_image=placeholder_filename)
    
    logger.info(f"Custom placeholder image uploaded by {admin.username}: {vid}")
    
    return RedirectResponse(url=f"/admin/videos", status_code=303)


@router.get("/payments", response_class=HTMLResponse)
async def admin_payments(
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Payment management page."""
    pending = await admin_service.get_pending_payments(db)
    purchases = await admin_service.get_purchases(db, limit=50)
    
    return templates.TemplateResponse(
        "admin/payments.html",
        {
            "request": request,
            "user": user,
            "pending_payments": pending,
            "purchases": purchases
        }
    )


@router.post("/payments/{invoice_id}/approve")
async def approve_payment(
    request: Request,
    invoice_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Manually approve payment."""
    try:
        inv_id = uuid.UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = await payment_service.get_invoice_by_id(db, inv_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    ip = get_client_ip(request)
    success = await admin_service.approve_payment(db, admin, invoice, ip)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to approve payment")
    
    return RedirectResponse(url="/admin/payments", status_code=303)


@router.post("/purchases/{purchase_id}/refund")
async def refund_purchase(
    request: Request,
    purchase_id: str,
    reason: str = Form(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Refund a purchase."""
    try:
        pur_id = uuid.UUID(purchase_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Purchase not found")
    
    purchase = await db.get(Purchase, pur_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    
    success = await payment_service.refund_purchase(db, purchase, reason)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to refund")
    
    return RedirectResponse(url="/admin/payments", status_code=303)


@router.get("/settings", response_class=HTMLResponse)
async def admin_settings(
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """System settings page."""
    config = await admin_service.get_system_config(db)
    
    return templates.TemplateResponse(
        "admin/settings.html",
        {
            "request": request,
            "user": user,
            "config": config
        }
    )


@router.post("/settings/update")
async def update_setting(
    request: Request,
    key: str = Form(...),
    value: str = Form(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update system setting."""
    ip = get_client_ip(request)
    success = await admin_service.update_config(db, admin, key, value, ip)
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update setting")
    
    return RedirectResponse(url="/admin/settings", status_code=303)


@router.get("/logs", response_class=HTMLResponse)
async def admin_logs(
    request: Request,
    action_type: str = Query(None),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Admin action logs."""
    logs = await admin_service.get_admin_logs(db, action_type=action_type)
    
    return templates.TemplateResponse(
        "admin/logs.html",
        {
            "request": request,
            "user": user,
            "logs": logs,
            "action_type": action_type
        }
    )


# ==================== CONTACT MESSAGES ====================
@router.get("/contacts", response_class=HTMLResponse)
async def admin_contacts(
    request: Request,
    page: int = Query(1, ge=1),
    is_read: str = Query(None),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Contact messages management page."""
    from app.models.admin import ContactMessage
    from sqlalchemy.orm import joinedload
    from sqlalchemy import select, desc, func
    
    limit = 50
    offset = (page - 1) * limit
    
    # Build query with eager loading
    query = select(ContactMessage).options(
        joinedload(ContactMessage.user)
    ).order_by(desc(ContactMessage.created_at))
    
    if is_read == "true":
        query = query.where(ContactMessage.is_read == True)
    elif is_read == "false":
        query = query.where(ContactMessage.is_read == False)
    
    # Execute query
    result = await db.execute(query.limit(limit).offset(offset))
    messages = result.unique().scalars().all()
    
    # Get total count
    total_result = await db.execute(select(func.count(ContactMessage.id)))
    total = total_result.scalar() or 0
    total_pages = (total + limit - 1) // limit
    
    # Get unread count
    unread_result = await db.execute(
        select(ContactMessage).where(ContactMessage.is_read == False)
    )
    unread_count = len(unread_result.scalars().all())
    
    return templates.TemplateResponse(
        "admin/contacts.html",
        {
            "request": request,
            "user": user,
            "messages": messages,
            "page": page,
            "is_read": is_read,
            "total_pages": total_pages,
            "total": total,
            "unread_count": unread_count
        }
    )


@router.post("/contacts/{message_id}/read")
async def mark_contact_read(
    request: Request,
    message_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Mark contact message as read."""
    from app.models.admin import ContactMessage
    
    try:
        msg_id = uuid.UUID(message_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Message not found")
    
    message = await db.get(ContactMessage, msg_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    message.is_read = True
    await db.commit()
    
    logger.info(f"Contact message marked as read by {admin.username}: {msg_id}")
    
    return RedirectResponse(url="/admin/contacts", status_code=303)


@router.post("/contacts/{message_id}/delete")
async def delete_contact(
    request: Request,
    message_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete contact message."""
    from app.models.admin import ContactMessage
    
    try:
        msg_id = uuid.UUID(message_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Message not found")
    
    message = await db.get(ContactMessage, msg_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    await db.delete(message)
    await db.commit()
    
    logger.info(f"Contact message deleted by {admin.username}: {msg_id}")
    
    return RedirectResponse(url="/admin/contacts", status_code=303)