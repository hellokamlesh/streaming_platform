# ============================================
# TorStream - Video Service
# ============================================

import uuid
import secrets
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.video import Video, VideoAccessType
from app.models.payment import Purchase
from app.models.user import User
from app.videos.processor import video_processor
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class VideoService:
    """Video business logic service."""
    
    def __init__(self):
        self.storage_path = Path(settings.VIDEO_STORAGE_PATH)
        self.preview_path = Path(settings.PREVIEW_STORAGE_PATH)
    
    def generate_filename(self, original_filename: str, mime_type: str) -> str:
        """Generate secure random filename."""
        ext = video_processor.get_file_extension(mime_type)
        random_name = secrets.token_urlsafe(24)
        return f"{random_name}{ext}"
    
    async def create_video(
        self,
        db: AsyncSession,
        title: str,
        description: Optional[str],
        filename: str,
        original_filename: str,
        file_size: int,
        mime_type: str,
        access_type: VideoAccessType,
        ppv_price: Optional[float],
        uploaded_by: Optional[uuid.UUID]
    ) -> Video:
        """Create new video record."""
        video = Video(
            id=uuid.uuid4(),
            title=title,
            description=description,
            filename=filename,
            original_filename=original_filename,
            file_size=file_size,
            mime_type=mime_type,
            access_type=access_type,
            ppv_price=ppv_price,
            is_active=True,
            is_processing=True,
            uploaded_by=uploaded_by
        )
        
        db.add(video)
        await db.commit()
        await db.refresh(video)
        
        logger.info(f"Video created: {video.id} - {title}")
        return video
    
    async def get_video_by_id(
        self,
        db: AsyncSession,
        video_id: uuid.UUID
    ) -> Optional[Video]:
        """Get video by ID."""
        result = await db.execute(
            select(Video).where(Video.id == video_id)
        )
        return result.scalar_one_or_none()
    
    async def get_public_videos(
        self,
        db: AsyncSession,
        limit: int = 20,
        offset: int = 0,
        access_type: Optional[VideoAccessType] = None
    ) -> List[Video]:
        """Get public videos with optional filtering."""
        query = select(Video).where(Video.is_active == True)
        
        if access_type:
            query = query.where(Video.access_type == access_type)
        
        query = query.order_by(desc(Video.created_at)).limit(limit).offset(offset)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def can_access_video(
        self,
        db: AsyncSession,
        video: Video,
        user: Optional[User]
    ) -> bool:
        """Check if user can access video."""
        
        # ===== PREMIUM USERS GET EVERYTHING! =====
        if user and user.is_premium_active:
            return True  # Premium users can access ANY video (including placeholders)
        
        # FREE VIDEOS REQUIRE LOGIN!
        if video.access_type == VideoAccessType.FREE:
            return user is not None  # ← CHANGED: must be logged in
        
        # Must be logged in for premium/PPV
        if not user:
            return False
        
        # Check PPV purchase for non-premium users
        if video.access_type == VideoAccessType.PPV:
            purchase = await db.execute(
                select(Purchase).where(
                    Purchase.user_id == user.id,
                    Purchase.video_id == video.id,
                    Purchase.is_refunded == False
                )
            )
            purchase = purchase.scalar_one_or_none()
            
            if purchase:
                # Check if purchase is still valid
                if purchase.expires_at:
                    return datetime.now(timezone.utc) < purchase.expires_at
                return True
            return False
        
        # Premium videos are only for premium users
        if video.access_type == VideoAccessType.PREMIUM:
            return False
        
        return False
    
    async def has_purchased(
        self,
        db: AsyncSession,
        video_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """Check if user has purchased video."""
        result = await db.execute(
            select(Purchase).where(
                Purchase.user_id == user_id,
                Purchase.video_id == video_id,
                Purchase.is_refunded == False
            )
        )
        purchase = result.scalar_one_or_none()
        
        if not purchase:
            return False
        
        if purchase.expires_at:
            return datetime.now(timezone.utc) < purchase.expires_at
        
        return True
    
    async def increment_view_count(
        self,
        db: AsyncSession,
        video_id: uuid.UUID
    ):
        """Increment video view count."""
        video = await self.get_video_by_id(db, video_id)
        if video:
            video.view_count += 1
            await db.commit()
    
    async def update_video(
        self,
        db: AsyncSession,
        video: Video,
        **kwargs
    ) -> Video:
        """Update video fields."""
        for key, value in kwargs.items():
            if hasattr(video, key):
                setattr(video, key, value)
        
        video.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(video)
        
        logger.info(f"Video updated: {video.id}")
        return video
    
    async def delete_video(
        self,
        db: AsyncSession,
        video: Video
    ) -> bool:
        """Delete video and associated files."""
        try:
            # Delete files
            video_path = self.storage_path / video.filename
            if video_path.exists():
                video_path.unlink()
            
            if video.preview_filename:
                preview_path = self.preview_path / video.preview_filename
                if preview_path.exists():
                    preview_path.unlink()
            
            if video.thumbnail_filename:
                thumbnail_path = self.preview_path / video.thumbnail_filename
                if thumbnail_path.exists():
                    thumbnail_path.unlink()
            
            # Delete custom blur/placeholder images
            if video.custom_blur_image:
                blur_path = self.preview_path / video.custom_blur_image
                if blur_path.exists():
                    blur_path.unlink()
            
            if video.placeholder_image:
                placeholder_path = self.preview_path / video.placeholder_image
                if placeholder_path.exists():
                    placeholder_path.unlink()
            
            # Delete database record
            await db.delete(video)
            await db.commit()
            
            logger.info(f"Video deleted: {video.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting video: {e}")
            return False
    
    async def search_videos(
        self,
        db: AsyncSession,
        query: str,
        limit: int = 20
    ) -> List[Video]:
        """Search videos by title."""
        search = f"%{query}%"
        result = await db.execute(
            select(Video)
            .where(
                Video.title.ilike(search),
                Video.is_active == True
            )
            .order_by(desc(Video.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    # ============================================
    # THUMBNAIL CONTROL FEATURES (ADDITIVE)
    # ============================================
    
    async def get_videos_filtered(
        self,
        db: AsyncSession,
        filter_type: str = "all",
        limit: int = 20,
        offset: int = 0
    ) -> List[Video]:
        """Get videos with filter support.
        
        filter_type options:
        - all: all videos
        - real: real videos (not placeholders)
        - placeholders: placeholder videos only
        - blurred: videos with blur enabled
        - auto_unblur_soon: videos scheduled to auto-unblur soon
        """
        query = select(Video).where(Video.is_active == True)
        
        if filter_type == "real":
            query = query.where(Video.is_placeholder == False)
        elif filter_type == "placeholders":
            query = query.where(Video.is_placeholder == True)
        elif filter_type == "blurred":
            query = query.where(Video.blur_level != "none")
        elif filter_type == "auto_unblur_soon":
            now = datetime.now(timezone.utc)
            query = query.where(
                Video.blur_until_date.isnot(None),
                Video.blur_until_date > now
            )
        
        query = query.order_by(desc(Video.created_at)).limit(limit).offset(offset)
        result = await db.execute(query)
        return result.scalars().all()
    
    def is_blur_active(self, video: Video) -> bool:
        """Check if blur is currently active for a video."""
        if video.blur_level == "none":
            return False
        
        # Check if blur_until_date has passed
        if video.blur_until_date:
            if datetime.now(timezone.utc) > video.blur_until_date:
                return False
        
        return True
    
    def get_duration_display(self, video: Video) -> str:
        """Get formatted duration string for display.
        
        Rules:
        - Placeholders: use fake_duration_seconds if set, else "Coming Soon"
        - Real videos: format from duration_seconds
        - < 60 min: MM:SS min format
        - >= 60 min: HH:MM:SS format
        """
        if video.is_placeholder:
            if video.fake_duration_seconds:
                return self._format_duration(video.fake_duration_seconds)
            return "Coming Soon"
        
        if video.duration_seconds:
            return self._format_duration(video.duration_seconds)
        
        return "Unknown"
    
    def _format_duration(self, seconds: int) -> str:
        """Format seconds into MM:SS min or HH:MM:SS."""
        if seconds < 3600:  # Less than 1 hour
            mins = seconds // 60
            secs = seconds % 60
            return f"{mins}:{secs:02d} min"
        else:  # 1 hour or more
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours}:{mins:02d}:{secs:02d}"


# Global video service instance
video_service = VideoService()