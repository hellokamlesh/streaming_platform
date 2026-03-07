# ============================================
# TorStream - Video Routes
# ============================================

import uuid
import os
from pathlib import Path
from fastapi import APIRouter, Request, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.models.video import Video, VideoAccessType
from app.auth.dependencies import require_auth, require_admin
from app.videos.service import video_service
from app.videos.processor import video_processor
from app.config import settings
from app.main import templates
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stream/{video_id}")
async def stream_video(
    request: Request,
    video_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """Stream video via X-Accel-Redirect."""
    try:
        vid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video = await video_service.get_video_by_id(db, vid)
    
    if not video or not video.is_active:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Check access
    can_access = await video_service.can_access_video(db, video, user)
    if not can_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Increment view count
    await video_service.increment_view_count(db, vid)
    
    # Return X-Accel-Redirect header
    response = Response()
    response.headers["X-Accel-Redirect"] = f"/videos/{video.filename}"
    response.headers["Content-Type"] = video.mime_type
    response.headers["Accept-Ranges"] = "bytes"
    
    return response


@router.get("/download/{video_id}")
async def download_video(
    request: Request,
    video_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """Download video (premium only)."""
    if not user.is_premium_active:
        raise HTTPException(status_code=403, detail="Premium required")
    
    try:
        vid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video = await video_service.get_video_by_id(db, vid)
    
    if not video or not video.is_active:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Check access
    can_access = await video_service.can_access_video(db, video, user)
    if not can_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Return X-Accel-Redirect with download header
    response = Response()
    response.headers["X-Accel-Redirect"] = f"/videos/{video.filename}"
    response.headers["Content-Type"] = video.mime_type
    response.headers["Content-Disposition"] = f'attachment; filename="{video.original_filename}"'
    
    return response


# ==================== Admin Video Routes ====================

@router.get("/upload", response_class=HTMLResponse)
async def upload_page(
    request: Request,
    user: User = Depends(require_admin)
):
    """Video upload page (admin only)."""
    if not settings.UPLOADS_ENABLED:
        return templates.TemplateResponse(
            "errors/maintenance.html",
            {"request": request, "message": "Uploads are currently disabled"}
        )
    
    return templates.TemplateResponse(
        "admin/upload.html",
        {
            "request": request,
            "user": user
        }
    )

@router.post("/upload")
async def upload_video(
    request: Request,
    title: str = Form(..., min_length=1, max_length=255),
    description: str = Form(None),
    access_type: str = Form("free"),
    ppv_price: float = Form(None),
    is_placeholder: str = Form("false"),
    placeholder_message: str = Form("Coming Soon"),
    fake_duration_seconds: str = Form(None),
    video_file: UploadFile = File(None),
    thumbnail_file: UploadFile = File(None),
    placeholder_image: UploadFile = File(None),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Handle video upload with optimization (admin only)."""
    if not settings.UPLOADS_ENABLED:
        raise HTTPException(status_code=403, detail="Uploads are disabled")
    
    # Check if this is a placeholder
    is_ph = is_placeholder.lower() == "true"
    
    # Validate: either video file OR placeholder
    if not is_ph and (not video_file or not video_file.filename):
        raise HTTPException(status_code=400, detail="Video file required for non-placeholder videos")
    
    # Initialize variables
    filename = None
    file_size = 0
    content_type = "application/octet-stream"
    duration = None
    preview_result = None
    thumbnail_result = None
    
    # Process video file if provided
    if video_file and video_file.filename:
        # Validate file size
        video_file.file.seek(0, 2)  # Seek to end
        file_size = video_file.file.tell()
        video_file.file.seek(0)  # Reset
        
        if file_size > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="File too large")
        
        # Validate MIME type
        content_type = video_file.content_type or "application/octet-stream"
        if not video_processor.validate_mime_type(content_type):
            raise HTTPException(status_code=400, detail="Invalid file type")
        
        # Generate secure filename
        filename = video_service.generate_filename(video_file.filename, content_type)
        file_path = Path(settings.VIDEO_STORAGE_PATH) / filename
        
        # Save file
        try:
            with open(file_path, "wb") as f:
                while chunk := await video_file.read(8192):
                    f.write(chunk)
        except Exception as e:
            logger.error(f"Error saving video: {e}")
            raise HTTPException(status_code=500, detail="Error saving video")
        
        # Verify file signature
        valid_sig, detected_mime = video_processor.verify_file_signature(str(file_path))
        if not valid_sig:
            # Delete file
            file_path.unlink()
            raise HTTPException(status_code=400, detail="File signature mismatch")
        
        # Strip metadata
        temp_path = str(file_path) + ".temp"
        if await video_processor.strip_metadata(str(file_path), temp_path):
            os.replace(temp_path, str(file_path))
        
        # OPTIMIZE VIDEO FOR STREAMING (re-encode with lower bitrate)
        optimized_path = str(file_path) + ".optimized"
        logger.info("Starting video optimization: %s", filename)
        if await video_processor.optimize_for_streaming(str(file_path), optimized_path):
            os.replace(optimized_path, str(file_path))
            logger.info("Video optimization complete: %s", filename)
        else:
            logger.warning("Video optimization failed, using original: %s", filename)
        
        # Get video duration
        duration = await video_processor.get_video_duration(str(file_path))
    else:
        # For placeholders without video, create dummy filename
        if is_ph:
            filename = f"placeholder_{uuid.uuid4()}"
        else:
            raise HTTPException(status_code=400, detail="Video file is required")
    
    # Create video record
    access_enum = VideoAccessType(access_type)
    video = await video_service.create_video(
        db=db,
        title=title,
        description=description,
        filename=filename,
        original_filename=video_file.filename if video_file else "placeholder",
        file_size=file_size,
        mime_type=content_type,
        access_type=access_enum,
        ppv_price=ppv_price if access_enum == VideoAccessType.PPV else None,
        uploaded_by=user.id
    )
    
    # Process placeholder image if provided
    placeholder_result = None
    if placeholder_image and placeholder_image.filename:
        logger.info(f"DEBUG: Attempting to save placeholder image: {placeholder_image.filename}")
        placeholder_filename = f"placeholder_{video.id}_{placeholder_image.filename}"
        placeholder_path = Path(settings.PREVIEW_STORAGE_PATH) / placeholder_filename
        logger.info(f"DEBUG: Placeholder path: {placeholder_path}")
        logger.info(f"DEBUG: Preview storage path exists: {Path(settings.PREVIEW_STORAGE_PATH).exists()}")
        try:
            with open(placeholder_path, "wb") as f:
                while chunk := await placeholder_image.read(8192):
                    f.write(chunk)
            placeholder_result = placeholder_filename
            logger.info("Placeholder image uploaded: %s", placeholder_filename)
        except Exception as e:
            logger.error("Error saving placeholder image: %s", e)
            placeholder_result = None
    else:
        logger.info(f"DEBUG: No placeholder image - placeholder_image={placeholder_image}, filename={placeholder_image.filename if placeholder_image else 'None'}")
    
    # Process regular thumbnail if provided
    if thumbnail_file and thumbnail_file.filename and not is_ph:
        thumbnail_filename = f"thumb_{video.id}.jpg"
        thumbnail_path = Path(settings.PREVIEW_STORAGE_PATH) / thumbnail_filename
        try:
            with open(thumbnail_path, "wb") as f:
                while chunk := await thumbnail_file.read(8192):
                    f.write(chunk)
            thumbnail_result = thumbnail_filename
            logger.info("Custom thumbnail uploaded: %s", thumbnail_filename)
        except Exception as e:
            logger.error("Error saving custom thumbnail: %s", e)
            thumbnail_result = None
    elif not is_ph and filename:
        # Auto-generate thumbnail from video
        thumbnail_filename = f"thumb_{video.id}.jpg"
        file_path = Path(settings.VIDEO_STORAGE_PATH) / filename
        thumbnail_result = await video_processor.generate_thumbnail(
            str(file_path), thumbnail_filename
        )
    
    # Generate preview only if video file exists
    if filename and video_file and video_file.filename:
        preview_filename = f"preview_{video.id}.mp4"
        file_path = Path(settings.VIDEO_STORAGE_PATH) / filename
        preview_result = await video_processor.generate_preview(
            str(file_path), preview_filename
        )
    
    # Parse fake duration
    fake_duration = None
    if is_ph and fake_duration_seconds:
        try:
            fake_duration = int(fake_duration_seconds)
        except ValueError:
            fake_duration = None
    
    # Update video with all settings
    update_data = {
        "preview_filename": preview_result,
        "thumbnail_filename": thumbnail_result or placeholder_result,
        "duration_seconds": duration,
        "is_processing": False,
        "is_placeholder": is_ph,
        "placeholder_message": placeholder_message if is_ph else None,
        "placeholder_image": placeholder_result if is_ph else None,
        "fake_duration_seconds": fake_duration if is_ph else None,
    }
    
    await video_service.update_video(db, video, **update_data)
    
    logger.info(f"Video uploaded: {video.id} by {user.username} (placeholder={is_ph})")
    
    return RedirectResponse(url=f"/video/{video.id}", status_code=303)


@router.post("/toggle/{video_id}")
async def toggle_video(
    request: Request,
    video_id: str,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Toggle video active status (admin only)."""
    from app.admin.service import admin_service
    
    try:
        vid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video = await video_service.get_video_by_id(db, vid)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    ip = request.client.host if request.client else None
    await admin_service.toggle_video_active(db, user, video, ip)
    
    return RedirectResponse(url="/admin/videos", status_code=303)
