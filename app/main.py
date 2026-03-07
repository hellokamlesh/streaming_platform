# ============================================
# TorStream - Main Application
# ============================================

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.database import init_db, close_db
from app.services.redis import redis_service
from app.auth.middleware import AuthMiddleware, CSRFMiddleware, TorSecurityMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting TorStream...")
    
    # Connect to Redis
    await redis_service.connect()
    
    # Initialize database
    await init_db()
    
    logger.info("TorStream started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down TorStream...")
    
    # Close Redis
    await redis_service.disconnect()
    
    # Close database
    await close_db()
    
    logger.info("TorStream shut down")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Tor-optimized secure video streaming platform",
    version="1.0.0",
    docs_url=None if not settings.DEBUG else "/docs",
    redoc_url=None if not settings.DEBUG else "/redoc",
    openapi_url=None if not settings.DEBUG else "/openapi.json",
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(AuthMiddleware)
app.add_middleware(TorSecurityMiddleware)
app.add_middleware(CSRFMiddleware)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Import and include routers
from app.routes import auth, public, user, video, payment, admin, api

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(video.router, prefix="/video", tags=["video"])  
app.include_router(user.router, prefix="/user", tags=["user"])
app.include_router(payment.router, prefix="/payment", tags=["payment"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(api.router, prefix="/api", tags=["api"])
app.include_router(public.router, tags=["public"]) 

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root redirect to home."""
    return RedirectResponse(url="/home")


@app.get("/home", response_class=HTMLResponse)
async def home(request: Request):
    """Public home page."""
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "redis": redis_service.is_available,
        "version": "1.0.0"
    }


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler."""
    if request.headers.get("accept", "").startswith("application/json"):
        return JSONResponse(
            status_code=404,
            content={"detail": "Not found"}
        )
    return templates.TemplateResponse(
        "errors/404.html",
        {"request": request},
        status_code=404
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    """Custom 500 handler."""
    logger.error(f"Server error: {exc}")
    if request.headers.get("accept", "").startswith("application/json"):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
    return templates.TemplateResponse(
        "errors/500.html",
        {"request": request},
        status_code=500
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        proxy_headers=True
    )
