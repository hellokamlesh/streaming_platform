# ============================================
# TorStream - BTCPay Client
# ============================================

import json
import hmac
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import httpx
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class BTCPayClient:
    """BTCPay Server API client."""
    
    def __init__(self):
        self.base_url = settings.BTCPAY_URL
        self.api_key = settings.BTCPAY_API_KEY
        self.store_id = settings.BTCPAY_STORE_ID
        self.webhook_secret = settings.BTCPAY_WEBHOOK_SECRET
        
        self.headers = {
            "Authorization": f"token {self.api_key}",
            "Content-Type": "application/json",
        }
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get HTTP client."""
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=30.0
        )
    
    async def create_invoice(
        self,
        amount: float,
        currency: str = "USD",
        order_id: str = None,
        buyer_email: str = None,
        metadata: Dict[str, Any] = None,
        expiration_minutes: int = 60
    ) -> Optional[Dict[str, Any]]:
        """
        Create BTCPay invoice.
        Returns invoice data or None on failure.
        """
        try:
            payload = {
                "amount": amount,
                "currency": currency,
                "metadata": metadata or {},
                "checkout": {
                    "expirationMinutes": expiration_minutes,
                    "monitoringMinutes": 60,
                    "paymentMethods": ["BTC"],
                }
            }
            
            if order_id:
                payload["metadata"]["orderId"] = order_id
            
            if buyer_email:
                payload["metadata"]["buyerEmail"] = buyer_email
            
            async with self._get_client() as client:
                response = await client.post(
                    f"/api/v1/stores/{self.store_id}/invoices",
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Invoice created: {data.get('id')}")
                    return data
                else:
                    logger.error(f"BTCPay create invoice error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"BTCPay create invoice exception: {e}")
            return None
    
    async def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Get invoice details."""
        try:
            async with self._get_client() as client:
                response = await client.get(
                    f"/api/v1/stores/{self.store_id}/invoices/{invoice_id}"
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"BTCPay get invoice error: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"BTCPay get invoice exception: {e}")
            return None
    
    async def refund_invoice(
        self,
        invoice_id: str,
        amount: float,
        currency: str = "USD"
    ) -> Optional[Dict[str, Any]]:
        """Refund an invoice."""
        try:
            payload = {
                "amount": amount,
                "currency": currency,
                "description": "Refund"
            }
            
            async with self._get_client() as client:
                response = await client.post(
                    f"/api/v1/stores/{self.store_id}/invoices/{invoice_id}/refund",
                    json=payload
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"BTCPay refund error: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"BTCPay refund exception: {e}")
            return None
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str
    ) -> bool:
        """Verify BTCPay webhook signature."""
        if not self.webhook_secret or not signature:
            return False
        
        try:
            expected = hmac.new(
                self.webhook_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected)
            
        except Exception as e:
            logger.error(f"Webhook signature verification error: {e}")
            return False
    
    def parse_webhook_payload(self, payload: bytes) -> Optional[Dict[str, Any]]:
        """Parse webhook payload."""
        try:
            return json.loads(payload)
        except json.JSONDecodeError as e:
            logger.error(f"Webhook payload parse error: {e}")
            return None


# Global BTCPay client instance
btcpay_client = BTCPayClient()
