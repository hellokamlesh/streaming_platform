import asyncio
import sys
sys.path.insert(0, '/app')

from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models.user import User
from app.services.security import hash_password
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
import uuid

async def create_admin():
    async with AsyncSessionLocal() as session:
        # Check if admin exists
        result = await session.execute(
            select(User).where(User.username == "admin")
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"User 'admin' already exists")
            return
        
        # Create admin user with default password
        admin = User(
            id=uuid.uuid4(),
            username="admin",
            password_hash=hash_password("admin123456"),
            is_admin=True,
            is_superadmin=True,
            is_premium=True,
            premium_expires_at=datetime.now(timezone.utc) + timedelta(days=3650),
            created_at=datetime.now(timezone.utc)
        )
        
        session.add(admin)
        await session.commit()
        print(f"Admin user created successfully!")
        print(f"Username: admin")
        print(f"Password: admin123456")

asyncio.run(create_admin())
