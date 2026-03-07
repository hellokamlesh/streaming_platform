# ============================================
# TorStream - User Routes
# ============================================

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.models.video import Video
from app.models.payment import Purchase
from app.models.payment import Invoice, Subscription
from app.auth.dependencies import require_auth, get_current_user
from app.payments.service import payment_service
from app.main import templates
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """User dashboard."""
    # Get recent purchases
    purchases_result = await db.execute(
        select(Purchase)
        .where(Purchase.user_id == user.id)
        .order_by(desc(Purchase.purchased_at))
        .limit(5)
    )
    purchases = purchases_result.scalars().all()
    
    # Get subscription info
    subscription_result = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.is_active == True
        )
        .order_by(desc(Subscription.expires_at))
    )
    subscription = subscription_result.scalar_one_or_none()
    
    return templates.TemplateResponse(
        "user/dashboard.html",
        {
            "request": request,
            "user": user,
            "purchases": purchases,
            "subscription": subscription,
            "is_premium_active": user.is_premium_active
        }
    )


@router.get("/purchases", response_class=HTMLResponse)
async def purchases(
    request: Request,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """User purchase history."""
    purchases_result = await db.execute(
        select(Purchase)
        .where(Purchase.user_id == user.id)
        .order_by(desc(Purchase.purchased_at))
    )
    purchases = purchases_result.scalars().all()
    
    return templates.TemplateResponse(
        "user/purchases.html",
        {
            "request": request,
            "user": user,
            "purchases": purchases
        }
    )


@router.get("/invoices", response_class=HTMLResponse)
async def invoices(
    request: Request,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """User invoices."""
    invoices = await payment_service.get_user_invoices(db, user.id)
    
    return templates.TemplateResponse(
        "user/invoices.html",
        {
            "request": request,
            "user": user,
            "invoices": invoices
        }
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: User = Depends(require_auth)
):
    """User settings page."""
    return templates.TemplateResponse(
        "user/settings.html",
        {
            "request": request,
            "user": user
        }
    )


@router.post("/settings/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(..., min_length=8),
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """Change user password."""
    from app.services.security import verify_password, hash_password
    
    # Verify current password
    if not verify_password(current_password, user.password_hash):
        return templates.TemplateResponse(
            "user/settings.html",
            {
                "request": request,
                "user": user,
                "error": "Current password is incorrect"
            }
        )
    
    # Update password
    user.password_hash = hash_password(new_password)
    await db.commit()
    
    logger.info(f"Password changed for user: {user.username}")
    
    return templates.TemplateResponse(
        "user/settings.html",
        {
            "request": request,
            "user": user,
            "success": "Password changed successfully"
        }
    )

@router.get("/subscription", response_class=HTMLResponse)
async def subscription(
    request: Request,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    """User subscription page."""
    from app.config import settings
    from app.models.payment import Subscription
    
    # Get active subscription from Subscription table
    subscription_result = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.is_active == True
        )
        .order_by(desc(Subscription.expires_at))
    )
    subscription = subscription_result.scalar_one_or_none()
    
    # If no subscription record, check if user has admin-set premium status
    if not subscription and user.is_premium_active:
        # Create a mock subscription object for the template
        class MockSubscription:
            is_valid = True
            subscription_type = "admin_premium"
            started_at = user.created_at
            expires_at = user.premium_expires_at
        
        subscription = MockSubscription()
    
    return templates.TemplateResponse(
        "user/subscription.html",
        {
            "request": request,
            "user": user,
            "subscription": subscription,
            "monthly_price": settings.PREMIUM_MONTHLY_PRICE,
            "yearly_price": settings.PREMIUM_YEARLY_PRICE
        }
    )