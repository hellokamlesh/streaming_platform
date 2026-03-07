# ============================================
# TorStream - Admin Models
# ============================================

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class AdminAction(Base):
    """Admin action audit log."""
    __tablename__ = "admin_actions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    target_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action_type = Column(String(50), nullable=False, index=True)
    action_description = Column(Text, nullable=False)
    action_data = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    admin = relationship("User", foreign_keys=[admin_id])
    target_user = relationship("User", foreign_keys=[target_user_id], back_populates="admin_actions")
    
    # Indexes
    __table_args__ = (
        Index('ix_admin_actions_admin_time', 'admin_id', 'created_at'),
        Index('ix_admin_actions_type_time', 'action_type', 'created_at'),
    )
    
    def __repr__(self):
        return f"<AdminAction(id={self.id}, type={self.action_type}, admin={self.admin_id})>"


class SystemConfig(Base):
    """System configuration settings."""
    __tablename__ = "system_config"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    value_type = Column(String(20), default="string", nullable=False)  # string, int, bool, json
    description = Column(Text, nullable=True)
    is_editable = Column(Boolean, default=True, nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Common configuration keys
    REGISTRATION_ENABLED = "registration_enabled"
    UPLOADS_ENABLED = "uploads_enabled"
    MAINTENANCE_MODE = "maintenance_mode"
    DEFAULT_PPV_PRICE = "default_ppv_price"
    PREMIUM_MONTHLY_PRICE = "premium_monthly_price"
    PREMIUM_YEARLY_PRICE = "premium_yearly_price"
    MAX_UPLOAD_SIZE_MB = "max_upload_size_mb"
    REQUIRE_CAPTCHA = "require_captcha"
    
    def __repr__(self):
        return f"<SystemConfig(key={self.key}, value={self.value})>"


class ContactMessage(Base):
    """User contact form submissions."""
    __tablename__ = "contact_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # ← REMOVED index=True
    ip_address = Column(String(45), nullable=False)
    name = Column(String(100), nullable=True)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    is_replied = Column(Boolean, default=False, nullable=False)
    admin_reply = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationship
    user = relationship("User", foreign_keys=[user_id])
    
    __table_args__ = (
        Index('ix_contact_messages_user_id', 'user_id'),  # ← This ONE index is enough
        Index('ix_contact_messages_ip_time', 'ip_address', 'created_at'),
        Index('ix_contact_messages_is_read', 'is_read'),
    )
    
    def __repr__(self):
        return f"<ContactMessage(id={self.id}, user={self.user_id}, ip={self.ip_address}, created={self.created_at})>"