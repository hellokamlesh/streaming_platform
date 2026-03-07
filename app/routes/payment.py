# ============================================
# TorStream - Payment Routes
# ============================================

import uuid
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.models.video import Video
from app.models.payment import Invoice
from app.auth.dependencies import require_auth
from app.payments.service import payment_service
from app.payments.btcpay import btcpay_client
from app.config import settings
from app.main import templates
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/buy/{video_id}", response_class=HTMLResponse)
async def buy_video_page(
    request: Request,
    video_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """PPV purchase page."""
    try:
        vid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video = await db.get(Video, vid)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Check if already purchased
    has_purchased = await payment_service.has_purchased(db, vid, user.id)
    if has_purchased:
        return RedirectResponse(url=f"/video/{video_id}", status_code=303)
    
    return templates.TemplateResponse(
        "payment/buy_video.html",
        {
            "request": request,
            "video": video,
            "user": user
        }
    )


@router.post("/buy/{video_id}")
async def buy_video(
    request: Request,
    video_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """Create PPV purchase invoice."""
    try:
        vid = uuid.UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video = await db.get(Video, vid)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Check if already purchased
    has_purchased = await payment_service.has_purchased(db, vid, user.id)
    if has_purchased:
        return RedirectResponse(url=f"/video/{video_id}", status_code=303)
    
    # Create invoice
    invoice = await payment_service.create_ppv_invoice(db, user, video)
    
    if not invoice:
        raise HTTPException(status_code=500, detail="Failed to create invoice")
    
    # Redirect to BTCPay checkout
    checkout_url = invoice.btcpay_data.get("checkoutLink") if invoice.btcpay_data else None
    if checkout_url:
        return RedirectResponse(url=checkout_url, status_code=303)
    
    # Fallback: show invoice details
    return templates.TemplateResponse(
        "payment/invoice.html",
        {
            "request": request,
            "invoice": invoice,
            "user": user
        }
    )

@router.get("/subscribe", response_class=HTMLResponse)
async def subscribe_page(
    request: Request,
    plan: str = "monthly",  # ADD THIS
    user: User = Depends(require_auth)
):
    """Subscription page with plan selection."""
    # Validate plan
    if plan not in ["monthly", "yearly"]:
        plan = "monthly"
    
    return templates.TemplateResponse(
        "payment/subscribe.html",
        {
            "request": request,
            "user": user,
            "selected_plan": plan,  # ADD THIS
            "monthly_price": settings.PREMIUM_MONTHLY_PRICE,
            "yearly_price": settings.PREMIUM_YEARLY_PRICE
        }
    )

@router.post("/subscribe")
async def subscribe(
    request: Request,
    plan: str = Form(...),  # monthly or yearly
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """Create subscription invoice."""
    if plan not in ("monthly", "yearly"):
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    # Create invoice
    invoice = await payment_service.create_subscription_invoice(db, user, plan)
    
    if not invoice:
        raise HTTPException(status_code=500, detail="Failed to create invoice")
    
    # Redirect to BTCPay checkout
    checkout_url = invoice.btcpay_data.get("checkoutLink") if invoice.btcpay_data else None
    if checkout_url:
        return RedirectResponse(url=checkout_url, status_code=303)
    
    return templates.TemplateResponse(
        "payment/invoice.html",
        {
            "request": request,
            "invoice": invoice,
            "user": user
        }
    )


@router.get("/invoice/{invoice_id}", response_class=HTMLResponse)
async def invoice_detail(
    request: Request,
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """Invoice detail page."""
    try:
        inv_id = uuid.UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = await payment_service.get_invoice_by_id(db, inv_id)
    
    if not invoice or invoice.user_id != user.id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Check latest status
    invoice = await payment_service.check_invoice_status(db, invoice)
    
    return templates.TemplateResponse(
        "payment/invoice.html",
        {
            "request": request,
            "invoice": invoice,
            "user": user
        }
    )


@router.post("/webhook")
async def btcpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """BTCPay webhook handler."""
    # Get raw body
    body = await request.body()
    
    # Verify signature
    signature = request.headers.get("BTCPay-Sig")
    if not btcpay_client.verify_webhook_signature(body, signature):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse payload
    payload = btcpay_client.parse_webhook_payload(body)
    if not payload:
        raise HTTPException(status_code=400, detail="Invalid payload")
    
    # Process webhook
    success = await payment_service.process_webhook(db, payload)
    
    if success:
        return {"status": "ok"}
    else:
        raise HTTPException(status_code=500, detail="Processing failed")


@router.get("/reconcile/{invoice_id}")
async def reconcile_invoice(
    request: Request,
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_auth)
):
    """Manual invoice reconciliation."""
    try:
        inv_id = uuid.UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = await payment_service.get_invoice_by_id(db, inv_id)
    
    if not invoice or invoice.user_id != user.id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Check and update status
    invoice = await payment_service.check_invoice_status(db, invoice)
    
    return RedirectResponse(
        url=f"/payment/invoice/{invoice_id}",
        status_code=303
    )
