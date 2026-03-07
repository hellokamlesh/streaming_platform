# ============================================
# TorStream - Admin Tests
# ============================================

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.admin.service import admin_service
from app.services.security import hash_password


@pytest.mark.asyncio
async def test_ban_user(client: AsyncClient, db_session: AsyncSession):
    """Test banning a user."""
    # Create admin and user
    admin = User(
        username="admin",
        password_hash=hash_password("adminpass"),
        is_admin=True
    )
    user = User(
        username="toban",
        password_hash=hash_password("userpass"),
        is_admin=False
    )
    db_session.add_all([admin, user])
    await db_session.commit()
    
    # Ban user
    success = await admin_service.ban_user(
        db_session, admin, user, "Test ban", "127.0.0.1"
    )
    assert success is True
    
    # Verify user is banned
    await db_session.refresh(user)
    assert user.is_banned is True
    assert user.ban_reason == "Test ban"


@pytest.mark.asyncio
async def test_grant_premium(client: AsyncClient, db_session: AsyncSession):
    """Test granting premium to user."""
    # Create admin and user
    admin = User(
        username="admin2",
        password_hash=hash_password("adminpass"),
        is_admin=True
    )
    user = User(
        username="getpremium",
        password_hash=hash_password("userpass"),
        is_premium=False
    )
    db_session.add_all([admin, user])
    await db_session.commit()
    
    # Grant premium
    success = await admin_service.grant_premium(
        db_session, admin, user, 30, "127.0.0.1"
    )
    assert success is True
    
    # Verify user has premium
    await db_session.refresh(user)
    assert user.is_premium is True
    assert user.premium_expires_at is not None


@pytest.mark.asyncio
async def test_superadmin_only_destructive(client: AsyncClient, db_session: AsyncSession):
    """Test that destructive actions require superadmin."""
    # Create regular admin (not superadmin)
    admin = User(
        username="regularadmin",
        password_hash=hash_password("adminpass"),
        is_admin=True,
        is_superadmin=False
    )
    db_session.add(admin)
    await db_session.commit()
    
    # Try to create another admin (should fail for non-superadmin)
    new_admin = await admin_service.create_admin(
        db_session, admin, "newadmin", "password123"
    )
    assert new_admin is None  # Should fail


@pytest.mark.asyncio
async def test_admin_action_logging(client: AsyncClient, db_session: AsyncSession):
    """Test admin actions are logged."""
    from app.models.admin import AdminAction
    
    # Create admin and user
    admin = User(
        username="loggingadmin",
        password_hash=hash_password("adminpass"),
        is_admin=True
    )
    user = User(
        username="loggeduser",
        password_hash=hash_password("userpass")
    )
    db_session.add_all([admin, user])
    await db_session.commit()
    
    # Perform action
    await admin_service.grant_premium(
        db_session, admin, user, 30, "127.0.0.1"
    )
    
    # Check log
    logs = await admin_service.get_admin_logs(db_session, limit=10)
    assert len(logs) > 0
    assert any(log.action_type == "grant_premium" for log in logs)
