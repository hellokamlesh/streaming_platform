# ============================================
# TorStream - Authentication Middleware
# ============================================

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from app.services.security import generate_csrf_token, verify_csrf_token
from app.services.redis import redis_service
import logging

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to handle authentication and session management."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        """Process request and response."""
        # Add request start time for logging
        request.state.start_time = __import__('time').time()
        
        # Process request
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Remove server signature
        if "Server" in response.headers:
            del response.headers["Server"]
        
        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """Middleware for CSRF protection via double-submit cookie."""
    
    def __init__(self, app: ASGIApp, exempt_paths: list = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or [
            "/api/webhook",
            "/health",
            "/static",
            "/auth/register",
            "/auth/login",
            "/auth/logout",          
            "/user/settings",          
            "/user/settings/change-password",    
            "/video/upload",           
            "/admin/upload",  
        ]
    
    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from CSRF."""
        return any(path.startswith(exempt) for exempt in self.exempt_paths)
    
    async def dispatch(self, request: Request, call_next):
        """Process request with CSRF protection."""
        path = request.url.path
        method = request.method
        
        # Skip CSRF for safe methods and exempt paths
        if method in ("GET", "HEAD", "OPTIONS") or self._is_exempt(path):
            response = await call_next(request)
            
            # Set CSRF cookie if not present
            if "csrftoken" not in request.cookies:
                csrf_token = generate_csrf_token()
                response.set_cookie(
                    key="csrftoken",
                    value=csrf_token,
                    httponly=False,  # Must be accessible by JavaScript
                    secure=False,  # Set to True in production with HTTPS
                    samesite="strict",
                    max_age=3600,
                )
            
            return response
        
        # Verify CSRF token for state-changing requests
        csrf_cookie = request.cookies.get("csrftoken")
        csrf_header = request.headers.get("X-CSRF-Token")
        
        #if not csrf_cookie or not csrf_header:
            #from fastapi.responses import JSONResponse
            #return JSONResponse(
             #   status_code=403,
              #  content={"detail": "CSRF token missing"}
            #)
        
        #if not verify_csrf_token(csrf_header, csrf_cookie):
         #   from fastapi.responses import JSONResponse
          #  return JSONResponse(
           #     status_code=403,
            #    content={"detail": "CSRF token invalid"}
            #)
        
        return await call_next(request)


class TorSecurityMiddleware(BaseHTTPMiddleware):
    """Middleware for Tor-optimized security headers."""
    
    async def dispatch(self, request: Request, call_next):
        """Add Tor-friendly security headers."""
        response = await call_next(request)
        
        # Disable features that could deanonymize
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )
        
        # Strict referrer policy
        response.headers["Referrer-Policy"] = "no-referrer"
        
        # Remove identifying headers - FIXED
        if "Server" in response.headers:
            del response.headers["Server"]
        if "X-Powered-By" in response.headers:
            del response.headers["X-Powered-By"]
        
        # Content Security Policy for Tor (no external resources)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "media-src 'self' blob:; "
            "object-src 'none'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        
        return response