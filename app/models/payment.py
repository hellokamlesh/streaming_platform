# ============================================
# TorStream - Payment Models
# ============================================

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Index, Text, Enum, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class InvoiceStatus(str, PyEnum):
    """BTCPay invoice statuses."""
    PENDING = "Pending"
    PROCESSING = "Processing"
    SETTLED = "Settled"
    EXPIRED = "Expired"
    INVALID = "Invalid"


class InvoiceType(str, PyEnum):
    """Type of invoice."""
    PPV = "ppv"
    SUBSCRIPTION_MONTHLY = "subscription_monthly"
    SUBSCRIPTION_YEARLY = "subscription_yearly"


class Purchase(Base):
    """Video purchase record."""
    __tablename__ = "purchases"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    price_paid = Column(Numeric(10, 2), nullable=False)
    purchased_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_refunded = Column(Boolean, default=False, nullable=False)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    refund_reason = Column(Text, nullable=True)
    
    # Relationships - use string references to avoid circular imports
    user = relationship("User", back_populates="purchases")
    video = relationship("Video", back_populates="purchases")
    invoice = relationship("Invoice", back_populates="purchase")
    
    # Indexes
    __table_args__ = (
        Index('ix_purchases_user_video', 'user_id', 'video_id', unique=True),
        Index('ix_purchases_purchased_at', 'purchased_at'),
    )
    
    @property
    def is_valid(self) -> bool:
        """Check if purchase is still valid."""
        if self.is_refunded:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True


class Invoice(Base):
    """BTCPay invoice record."""
    __tablename__ = "invoices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    btcpay_invoice_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_type = Column(Enum(InvoiceType), nullable=False)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="SET NULL"), nullable=True, index=True)
    amount_usd = Column(Numeric(10, 2), nullable=False)
    amount_btc = Column(Numeric(20, 8), nullable=True)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.PENDING, nullable=False, index=True)
    is_processed = Column(Boolean, default=False, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    btcpay_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    user = relationship("User")
    video = relationship("Video")
    purchase = relationship("Purchase", back_populates="invoice", uselist=False)
    subscription = relationship("Subscription", back_populates="invoice", uselist=False)
    payment_logs = relationship("PaymentLog", back_populates="invoice", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('ix_invoices_user_status', 'user_id', 'status'),
        Index('ix_invoices_created_at', 'created_at'),
        Index('ix_invoices_status_processed', 'status', 'is_processed'),
    )
    
    def __repr__(self):
        return f"<Invoice(id={self.id}, btcpay_id={self.btcpay_invoice_id}, status={self.status})>"


class Subscription(Base):
    """Premium subscription record."""
    __tablename__ = "subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    subscription_type = Column(String(20), nullable=False)
    price_paid = Column(Numeric(10, 2), nullable=False)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_cancelled = Column(Boolean, default=False, nullable=False)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    auto_renew = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")
    invoice = relationship("Invoice", back_populates="subscription")
    
    # Indexes
    __table_args__ = (
        Index('ix_subscriptions_user_active', 'user_id', 'is_active'),
        Index('ix_subscriptions_expires_at', 'expires_at'),
    )
    
    @property
    def is_valid(self) -> bool:
        """Check if subscription is still valid."""
        if not self.is_active or self.is_cancelled:
            return False
        return datetime.now(timezone.utc) < self.expires_at


class PaymentLog(Base):
    """Payment event logging for audit."""
    __tablename__ = "payment_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    event_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="payment_logs")
    
    # Indexes
    __table_args__ = (
        Index('ix_payment_logs_invoice_event', 'invoice_id', 'event_type'),
        Index('ix_payment_logs_created_at', 'created_at'),
    )
