# ============================================
# TorStream - Video Models
# ============================================

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Index, Text, Enum, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class VideoAccessType(str, PyEnum):
    """Video access types."""
    FREE = "free"
    PPV = "ppv"
    PREMIUM = "premium"


class Video(Base):
    """Video content model."""
    __tablename__ = "videos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    filename = Column(String(255), nullable=False, unique=True)
    original_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    duration_seconds = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=False)
    access_type = Column(Enum(VideoAccessType), default=VideoAccessType.FREE, nullable=False)
    ppv_price = Column(Numeric(10, 2), nullable=True)
    thumbnail_filename = Column(String(255), nullable=True)
    preview_filename = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_processing = Column(Boolean, default=False, nullable=False)
    processing_error = Column(Text, nullable=True)
    view_count = Column(Integer, default=0, nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Placeholder settings
    is_placeholder = Column(Boolean, default=False, nullable=False)
    placeholder_message = Column(String(255), nullable=True, default="Coming Soon")
    placeholder_image = Column(String(255), nullable=True)
    fake_duration_seconds = Column(Integer, nullable=True)
    
    # Blur settings
    blur_level = Column(String(20), default="none", nullable=False)
    blur_until_date = Column(DateTime(timezone=True), nullable=True)
    custom_blur_image = Column(String(255), nullable=True)
    
    # Relationships
    uploader = relationship("User", foreign_keys=[uploaded_by])
    purchases = relationship("Purchase", back_populates="video", cascade="all, delete-orphan")
    video_access = relationship("VideoAccess", back_populates="video", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('ix_videos_access_type_active', 'access_type', 'is_active'),
        Index('ix_videos_created_at', 'created_at'),
        Index('ix_videos_uploaded_by', 'uploaded_by'),
    )
    
    def __repr__(self):
        return f"<Video(id={self.id}, title={self.title}, access_type={self.access_type})>"


class VideoAccess(Base):
    """Video access permissions for users (granted via purchase or subscription)."""
    __tablename__ = "video_access"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    access_type = Column(String(20), nullable=False)  # 'purchase', 'subscription', 'admin_grant'
    purchase_id = Column(UUID(as_uuid=True), ForeignKey("purchases.id", ondelete="SET NULL"), nullable=True)
    granted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="video_access")
    video = relationship("Video", back_populates="video_access")
    purchase = relationship("Purchase")
    
    # Indexes
    __table_args__ = (
        Index('ix_video_access_user_video', 'user_id', 'video_id', unique=True),
        Index('ix_video_access_granted_at', 'granted_at'),
    )
    
    @property
    def is_valid(self) -> bool:
        """Check if access is still valid."""
        if not self.is_active:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True
