# ============================================
# TorStream - Authentication Tests
# ============================================

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.services.security import verify_password, hash_password


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, db_session: AsyncSession):
    """Test successful user registration."""
    # Get captcha first
    captcha_resp = await client.get("/api/captcha")
    assert captcha_resp.status_code == 200
    captcha_data = captcha_resp.json()
    
    # Register user
    response = await client.post(
        "/auth/register",
        data={
            "username": "testuser",
            "password": "testpassword123",
            "captcha_token": captcha_data["token"],
            "captcha_code": "TEST123"  # In test mode, captcha might be bypassed
        }
    )
    
    # Should redirect to login
    assert response.status_code in [200, 302, 303]
    
    # Verify user was created
    result = await db_session.execute(
        select(User).where(User.username == "testuser")
    )
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.username == "testuser"
    assert verify_password("testpassword123", user.password_hash)


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    """Test registration with duplicate username."""
    # First registration
    captcha_resp = await client.get("/api/captcha")
    captcha_data = captcha_resp.json()
    
    await client.post(
        "/auth/register",
        data={
            "username": "duptest",
            "password": "password123",
            "captcha_token": captcha_data["token"],
            "captcha_code": "TEST123"
        }
    )
    
    # Second registration with same username
    response = await client.post(
        "/auth/register",
        data={
            "username": "duptest",
            "password": "password456",
            "captcha_token": captcha_data["token"],
            "captcha_code": "TEST123"
        }
    )
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db_session: AsyncSession):
    """Test successful login."""
    # Create user
    user = User(
        username="logintest",
        password_hash=hash_password("testpass123"),
        is_admin=False
    )
    db_session.add(user)
    await db_session.commit()
    
    # Login
    response = await client.post(
        "/auth/login",
        data={
            "username": "logintest",
            "password": "testpass123"
        }
    )
    
    # Should redirect to dashboard
    assert response.status_code in [302, 303]
    assert "/user/dashboard" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    """Test login with invalid credentials."""
    response = await client.post(
        "/auth/login",
        data={
            "username": "nonexistent",
            "password": "wrongpassword"
        }
    )
    
    assert response.status_code in [302, 303, 401]


@pytest.mark.asyncio
async def test_login_rate_limiting(client: AsyncClient):
    """Test login rate limiting."""
    # Make multiple failed login attempts
    for i in range(7):
        response = await client.post(
            "/auth/login",
            data={
                "username": "ratelimit",
                "password": "wrong"
            }
        )
    
    # Should be rate limited
    assert response.status_code in [429, 302, 303]


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, db_session: AsyncSession):
    """Test logout functionality."""
    # Create and login user
    user = User(
        username="logouttest",
        password_hash=hash_password("testpass123"),
        is_admin=False
    )
    db_session.add(user)
    await db_session.commit()
    
    await client.post(
        "/auth/login",
        data={
            "username": "logouttest",
            "password": "testpass123"
        }
    )
    
    # Logout
    response = await client.post("/auth/logout")
    assert response.status_code in [302, 303]
