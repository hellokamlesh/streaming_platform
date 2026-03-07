# ============================================
# TorStream - Video Tests
# ============================================

import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.video import Video, VideoAccessType, Purchase
from app.videos.service import video_service
from app.services.security import hash_password


@pytest.mark.asyncio
async def test_video_access_free(client: AsyncClient, db_session: AsyncSession):
    """Test free video access."""
    # Create free video
    video = Video(
        id=uuid.uuid4(),
        title="Free Video",
        filename="free.mp4",
        original_filename="free.mp4",
        file_size=1000,
        mime_type="video/mp4",
        access_type=VideoAccessType.FREE,
        is_active=True
    )
    db_session.add(video)
    await db_session.commit()
    
    # Anyone should be able to access
    can_access = await video_service.can_access_video(db_session, video, None)
    assert can_access is True


@pytest.mark.asyncio
async def test_video_access_premium(client: AsyncClient, db_session: AsyncSession):
    """Test premium video access."""
    # Create premium video
    video = Video(
        id=uuid.uuid4(),
        title="Premium Video",
        filename="premium.mp4",
        original_filename="premium.mp4",
        file_size=1000,
        mime_type="video/mp4",
        access_type=VideoAccessType.PREMIUM,
        is_active=True
    )
    
    # Create users
    free_user = User(
        username="freeuser",
        password_hash=hash_password("testpass"),
        is_premium=False
    )
    premium_user = User(
        username="premiumuser",
        password_hash=hash_password("testpass"),
        is_premium=True
    )
    
    db_session.add_all([video, free_user, premium_user])
    await db_session.commit()
    
    # Free user should not access
    can_access_free = await video_service.can_access_video(db_session, video, free_user)
    assert can_access_free is False
    
    # Premium user should access
    can_access_premium = await video_service.can_access_video(db_session, video, premium_user)
    assert can_access_premium is True


@pytest.mark.asyncio
async def test_video_access_ppv(client: AsyncClient, db_session: AsyncSession):
    """Test PPV video access."""
    # Create PPV video
    video = Video(
        id=uuid.uuid4(),
        title="PPV Video",
        filename="ppv.mp4",
        original_filename="ppv.mp4",
        file_size=1000,
        mime_type="video/mp4",
        access_type=VideoAccessType.PPV,
        ppv_price=4.99,
        is_active=True
    )
    
    # Create user
    user = User(
        username="ppvuser",
        password_hash=hash_password("testpass"),
        is_premium=False
    )
    
    db_session.add_all([video, user])
    await db_session.commit()
    
    # User without purchase should not access
    can_access = await video_service.can_access_video(db_session, video, user)
    assert can_access is False
    
    # Create purchase
    purchase = Purchase(
        id=uuid.uuid4(),
        user_id=user.id,
        video_id=video.id,
        price_paid=4.99
    )
    db_session.add(purchase)
    await db_session.commit()
    
    # User with purchase should access
    can_access_after = await video_service.can_access_video(db_session, video, user)
    assert can_access_after is True


@pytest.mark.asyncio
async def test_video_search(client: AsyncClient, db_session: AsyncSession):
    """Test video search."""
    # Create videos
    video1 = Video(
        id=uuid.uuid4(),
        title="Python Tutorial",
        filename="py.mp4",
        original_filename="py.mp4",
        file_size=1000,
        mime_type="video/mp4",
        access_type=VideoAccessType.FREE,
        is_active=True
    )
    video2 = Video(
        id=uuid.uuid4(),
        title="JavaScript Guide",
        filename="js.mp4",
        original_filename="js.mp4",
        file_size=1000,
        mime_type="video/mp4",
        access_type=VideoAccessType.FREE,
        is_active=True
    )
    
    db_session.add_all([video1, video2])
    await db_session.commit()
    
    # Search for Python
    results = await video_service.search_videos(db_session, "python")
    assert len(results) >= 1
    assert any(v.title == "Python Tutorial" for v in results)
