# ============================================
# HotStream - Configuration
# ============================================

import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application
    APP_NAME: str = "HotStream"
    DEBUG: bool = False
    SECRET_KEY: str = Field(..., min_length=32)
    ADMIN_SECRET_KEY: str = Field(..., min_length=32)
    
    # Database
    DATABASE_URL: str = Field(..., pattern=r"^postgresql\+asyncpg://")
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # BTCPay
    BTCPAY_URL: Optional[str] = None
    BTCPAY_API_KEY: Optional[str] = None
    BTCPAY_STORE_ID: Optional[str] = None
    BTCPAY_WEBHOOK_SECRET: Optional[str] = None
    
    # Pricing
    PREMIUM_MONTHLY_PRICE: float = 9.99
    PREMIUM_YEARLY_PRICE: float = 99.99
    
    # Storage
    VIDEO_STORAGE_PATH: str = "/app/static/uploads"
    PREVIEW_STORAGE_PATH: str = "/app/static/previews"
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024 * 1024  # 5GB
    
    # Security
    ARGON2_TIME_COST: int = 2
    ARGON2_MEMORY_COST: int = 65536
    ARGON2_PARALLELISM: int = 1
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Rate Limiting
    LOGIN_RATE_LIMIT: int = 5
    LOGIN_RATE_LIMIT_WINDOW: int = 900  # 15 minutes
    
    # Tor
    TOR_HOSTNAME: Optional[str] = None
    
    # Feature Flags
    REGISTRATION_ENABLED: bool = True
    UPLOADS_ENABLED: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @validator("SECRET_KEY", "ADMIN_SECRET_KEY")
    def validate_secret_key(cls, v):
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters")
        return v
    
    @property
    def jwt_algorithm(self) -> str:
        return "HS256"
    
    @property
    def cookie_settings(self) -> dict:
        """HTTP-only cookie settings for production."""
        return {
            "httponly": True,
            "secure": not self.DEBUG,
            "samesite": "strict",
            "max_age": self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
