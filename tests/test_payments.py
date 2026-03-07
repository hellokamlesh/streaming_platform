# ============================================
# TorStream - Payment Tests
# ============================================

import pytest
import uuid
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.video import Video, VideoAccessType
from app.models.payment import Invoice, InvoiceStatus, Purchase
from app.services.security import hash_password
from app.payments.service import payment_service


@pytest.mark.asyncio
async def test_create_ppv_invoice(client: AsyncClient, db_session: AsyncSession):
    """Test creating PPV invoice."""
    # Create user and video
    user = User(
        username="ppvuser",
        password_hash=hash_password("testpass"),
        is_admin=False
    )
    video = Video(
        id=uuid.uuid4(),
        title="Test Video",
        filename="test.mp4",
        original_filename="test.mp4",
        file_size=1000,
        mime_type="video/mp4",
        access_type=VideoAccessType.PPV,
        ppv_price=4.99,
        is_active=True
    )
    db_session.add_all([user, video])
    await db_session.commit()
    
    # Create invoice (mock BTCPay)
    invoice = Invoice(
        id=uuid.uuid4(),
        btcpay_invoice_id="test_invoice_123",
        user_id=user.id,
        invoice_type="ppv",
        video_id=video.id,
        amount_usd=4.99,
        status=InvoiceStatus.PENDING,
        is_processed=False,
        expires_at=datetime.now(timezone.utc)
    )
    db_session.add(invoice)
    await db_session.commit()
    
    # Verify invoice was created
    result = await db_session.execute(
        select(Invoice).where(Invoice.id == invoice.id)
    )
    saved_invoice = result.scalar_one_or_none()
    assert saved_invoice is not None
    assert saved_invoice.amount_usd == 4.99


@pytest.mark.asyncio
async def test_payment_idempotency(client: AsyncClient, db_session: AsyncSession):
    """Test payment processing idempotency."""
    # Create user
    user = User(
        username="idempotent",
        password_hash=hash_password("testpass"),
        is_admin=False
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create invoice
    invoice = Invoice(
        id=uuid.uuid4(),
        btcpay_invoice_id="idempotent_test_123",
        user_id=user.id,
        invoice_type="subscription_monthly",
        amount_usd=9.99,
        status=InvoiceStatus.SETTLED,
        is_processed=False,
        expires_at=datetime.now(timezone.utc)
    )
    db_session.add(invoice)
    await db_session.commit()
    
    # Process webhook first time
    webhook_data = {
        "invoiceId": "idempotent_test_123",
        "type": "InvoiceSettled",
        "status": "Settled"
    }
    
    success1 = await payment_service.process_webhook(db_session, webhook_data)
    assert success1 is True
    
    # Verify user got premium
    await db_session.refresh(user)
    assert user.is_premium is True
    
    # Process same webhook again (should be idempotent)
    success2 = await payment_service.process_webhook(db_session, webhook_data)
    assert success2 is True  # Should succeed but not duplicate


@pytest.mark.asyncio
async def test_subscription_expiration(client: AsyncClient, db_session: AsyncSession):
    """Test subscription expiration logic."""
    from datetime import timedelta
    
    # Create user with expired premium
    user = User(
        username="expired",
        password_hash=hash_password("testpass"),
        is_premium=True,
        premium_expires_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    db_session.add(user)
    await db_session.commit()
    
    # Check premium status
    assert user.is_premium_active is False
