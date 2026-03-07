# ============================================
# TorStream - Payment Service
# ============================================

import uuid
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.payment import Invoice, InvoiceStatus, InvoiceType, Subscription, PaymentLog
from app.models.video import Video
from app.models.payment import Purchase
from app.models.user import User
from app.payments.btcpay import btcpay_client
from app.config import settings
from app.services.redis import redis_service
import logging

logger = logging.getLogger(__name__)


class PaymentService:
    """Payment business logic with idempotent processing."""
    
    async def create_ppv_invoice(
        self,
        db: AsyncSession,
        user: User,
        video: Video
    ) -> Optional[Invoice]:
        """Create PPV purchase invoice."""
        if not video.ppv_price:
            logger.error(f"Video {video.id} has no PPV price")
            return None
        
        # Check if user already has valid purchase
        existing = await db.execute(
            select(Purchase).where(
                Purchase.user_id == user.id,
                Purchase.video_id == video.id,
                Purchase.is_refunded == False
            )
        )
        if existing.scalar_one_or_none():
            logger.info(f"User {user.id} already purchased video {video.id}")
            return None
        
        # Create BTCPay invoice
        btcpay_invoice = await btcpay_client.create_invoice(
            amount=float(video.ppv_price),
            order_id=f"ppv-{user.id}-{video.id}",
            metadata={
                "user_id": str(user.id),
                "video_id": str(video.id),
                "invoice_type": "ppv"
            },
            expiration_minutes=60
        )
        
        if not btcpay_invoice:
            return None
        
        # Create invoice record
        invoice = Invoice(
            id=uuid.uuid4(),
            btcpay_invoice_id=btcpay_invoice["id"],
            user_id=user.id,
            invoice_type=InvoiceType.PPV,
            video_id=video.id,
            amount_usd=video.ppv_price,
            amount_btc=btcpay_invoice.get("amount"),
            status=InvoiceStatus.PENDING,
            is_processed=False,
            btcpay_data=btcpay_invoice,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        
        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)
        
        # Log payment event
        await self._log_payment_event(db, invoice.id, "invoice_created", btcpay_invoice)
        
        logger.info(f"PPV invoice created: {invoice.id} for video {video.id}")
        return invoice
    
    async def create_subscription_invoice(
        self,
        db: AsyncSession,
        user: User,
        subscription_type: str  # "monthly" or "yearly"
    ) -> Optional[Invoice]:
        """Create subscription invoice."""
        if subscription_type == "monthly":
            amount = Decimal(str(settings.PREMIUM_MONTHLY_PRICE))
            invoice_type = InvoiceType.SUBSCRIPTION_MONTHLY
        elif subscription_type == "yearly":
            amount = Decimal(str(settings.PREMIUM_YEARLY_PRICE))
            invoice_type = InvoiceType.SUBSCRIPTION_YEARLY
        else:
            logger.error(f"Invalid subscription type: {subscription_type}")
            return None
        
        # Create BTCPay invoice
        btcpay_invoice = await btcpay_client.create_invoice(
            amount=float(amount),
            order_id=f"sub-{user.id}-{subscription_type}",
            metadata={
                "user_id": str(user.id),
                "subscription_type": subscription_type,
                "invoice_type": "subscription"
            },
            expiration_minutes=60
        )
        
        if not btcpay_invoice:
            return None
        
        # Create invoice record
        invoice = Invoice(
            id=uuid.uuid4(),
            btcpay_invoice_id=btcpay_invoice["id"],
            user_id=user.id,
            invoice_type=invoice_type,
            video_id=None,
            amount_usd=amount,
            amount_btc=btcpay_invoice.get("amount"),
            status=InvoiceStatus.PENDING,
            is_processed=False,
            btcpay_data=btcpay_invoice,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        
        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)
        
        # Log payment event
        await self._log_payment_event(db, invoice.id, "invoice_created", btcpay_invoice)
        
        logger.info(f"Subscription invoice created: {invoice.id} ({subscription_type})")
        return invoice
    
    async def process_webhook(
        self,
        db: AsyncSession,
        payload: dict
    ) -> bool:
        """
        Process BTCPay webhook with idempotency.
        Returns True if processed successfully.
        """
        btcpay_invoice_id = payload.get("invoiceId")
        if not btcpay_invoice_id:
            logger.error("Webhook missing invoiceId")
            return False
        
        # Get invoice from database
        result = await db.execute(
            select(Invoice).where(Invoice.btcpay_invoice_id == btcpay_invoice_id)
        )
        invoice = result.scalar_one_or_none()
        
        if not invoice:
            logger.error(f"Invoice not found: {btcpay_invoice_id}")
            return False
        
        # Check idempotency - already processed
        if invoice.is_processed:
            logger.info(f"Invoice {invoice.id} already processed, ignoring")
            return True
        
        # Get new status
        new_status = payload.get("type", "").replace("Invoice", "").upper()
        if not new_status:
            new_status = payload.get("status", "")
        
        # Map BTCPay status to our status
        status_map = {
            "NEW": InvoiceStatus.PENDING,
            "PENDING": InvoiceStatus.PENDING,
            "PROCESSING": InvoiceStatus.PROCESSING,
            "SETTLED": InvoiceStatus.SETTLED,
            "EXPIRED": InvoiceStatus.EXPIRED,
            "INVALID": InvoiceStatus.INVALID,
        }
        
        invoice.status = status_map.get(new_status, InvoiceStatus.PENDING)
        
        # Log the webhook event
        await self._log_payment_event(db, invoice.id, f"webhook_{new_status.lower()}", payload)
        
        # Process settled invoice
        if invoice.status == InvoiceStatus.SETTLED and not invoice.is_processed:
            success = await self._process_settled_invoice(db, invoice)
            if success:
                invoice.is_processed = True
                invoice.processed_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info(f"Invoice {invoice.id} processed successfully")
            return success
        
        await db.commit()
        return True
    
    async def _process_settled_invoice(
        self,
        db: AsyncSession,
        invoice: Invoice
    ) -> bool:
        """Process settled invoice - grant access."""
        try:
            if invoice.invoice_type == InvoiceType.PPV:
                return await self._process_ppv_purchase(db, invoice)
            elif invoice.invoice_type in (InvoiceType.SUBSCRIPTION_MONTHLY, InvoiceType.SUBSCRIPTION_YEARLY):
                return await self._process_subscription(db, invoice)
            
            return False
            
        except Exception as e:
            logger.error(f"Error processing settled invoice {invoice.id}: {e}")
            return False
    
    async def _process_ppv_purchase(
        self,
        db: AsyncSession,
        invoice: Invoice
    ) -> bool:
        """Process PPV purchase."""
        # Create purchase record
        purchase = Purchase(
            id=uuid.uuid4(),
            user_id=invoice.user_id,
            video_id=invoice.video_id,
            invoice_id=invoice.id,
            price_paid=invoice.amount_usd,
            purchased_at=datetime.now(timezone.utc),
            expires_at=None  # PPV purchases don't expire
        )
        
        db.add(purchase)
        await db.commit()
        
        logger.info(f"PPV purchase created: {purchase.id} for video {invoice.video_id}")
        return True
    
    async def _process_subscription(
        self,
        db: AsyncSession,
        invoice: Invoice
    ) -> bool:
        """Process subscription payment."""
        # Determine subscription duration
        if invoice.invoice_type == InvoiceType.SUBSCRIPTION_MONTHLY:
            duration_days = 30
            sub_type = "monthly"
        else:
            duration_days = 365
            sub_type = "yearly"
        
        # Get user
        result = await db.execute(
            select(User).where(User.id == invoice.user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.error(f"User not found for subscription: {invoice.user_id}")
            return False
        
        # Calculate expiration
        now = datetime.now(timezone.utc)
        
        # If user has active premium, extend from current expiration
        if user.is_premium and user.premium_expires_at and user.premium_expires_at > now:
            expires_at = user.premium_expires_at + timedelta(days=duration_days)
        else:
            expires_at = now + timedelta(days=duration_days)
        
        # Update user
        user.is_premium = True
        user.premium_expires_at = expires_at
        
        # Create subscription record
        subscription = Subscription(
            id=uuid.uuid4(),
            user_id=invoice.user_id,
            invoice_id=invoice.id,
            subscription_type=sub_type,
            price_paid=invoice.amount_usd,
            started_at=now,
            expires_at=expires_at,
            is_active=True,
            is_cancelled=False,
            auto_renew=False
        )
        
        db.add(subscription)
        await db.commit()
        
        logger.info(f"Subscription activated for user {user.id} until {expires_at}")
        return True
    
    async def refund_purchase(
        self,
        db: AsyncSession,
        purchase: Purchase,
        reason: str
    ) -> bool:
        """Refund a purchase."""
        if purchase.is_refunded:
            logger.info(f"Purchase {purchase.id} already refunded")
            return False
        
        # Get invoice
        if not purchase.invoice_id:
            logger.error(f"Purchase {purchase.id} has no invoice")
            return False
        
        result = await db.execute(
            select(Invoice).where(Invoice.id == purchase.invoice_id)
        )
        invoice = result.scalar_one_or_none()
        
        if not invoice:
            logger.error(f"Invoice not found for purchase {purchase.id}")
            return False
        
        # Process refund via BTCPay
        refund_result = await btcpay_client.refund_invoice(
            invoice.btcpay_invoice_id,
            float(purchase.price_paid)
        )
        
        if not refund_result:
            logger.error(f"BTCPay refund failed for invoice {invoice.id}")
            return False
        
        # Update purchase
        purchase.is_refunded = True
        purchase.refunded_at = datetime.now(timezone.utc)
        purchase.refund_reason = reason
        
        await db.commit()
        
        # Log refund
        await self._log_payment_event(db, invoice.id, "refund_processed", {
            "purchase_id": str(purchase.id),
            "reason": reason,
            "amount": float(purchase.price_paid)
        })
        
        logger.info(f"Purchase {purchase.id} refunded")
        return True
    
    async def get_user_invoices(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 20
    ) -> List[Invoice]:
        """Get user's invoices."""
        result = await db.execute(
            select(Invoice)
            .where(Invoice.user_id == user_id)
            .order_by(desc(Invoice.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_invoice_by_id(
        self,
        db: AsyncSession,
        invoice_id: uuid.UUID
    ) -> Optional[Invoice]:
        """Get invoice by ID."""
        result = await db.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        )
        return result.scalar_one_or_none()
    
    async def check_invoice_status(
        self,
        db: AsyncSession,
        invoice: Invoice
    ) -> Invoice:
        """Check and update invoice status from BTCPay."""
        btcpay_data = await btcpay_client.get_invoice(invoice.btcpay_invoice_id)
        
        if btcpay_data:
            invoice.btcpay_data = btcpay_data
            
            # Update status
            status = btcpay_data.get("status", "").upper()
            if status == "SETTLED":
                invoice.status = InvoiceStatus.SETTLED
            elif status == "EXPIRED":
                invoice.status = InvoiceStatus.EXPIRED
            elif status == "INVALID":
                invoice.status = InvoiceStatus.INVALID
            
            await db.commit()
        
        return invoice
    
    async def _log_payment_event(
        self,
        db: AsyncSession,
        invoice_id: uuid.UUID,
        event_type: str,
        event_data: dict
    ):
        """Log payment event."""
        log = PaymentLog(
            id=uuid.uuid4(),
            invoice_id=invoice_id,
            event_type=event_type,
            event_data=event_data
        )
        db.add(log)
        await db.commit()


# Global payment service instance
payment_service = PaymentService()
