#!/bin/bash
# ============================================
# TorStream - Initialize Admin User
# ============================================

set -e

# Default credentials (change these!)
ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(openssl rand -base64 32)}"

echo "Creating admin user: $ADMIN_USERNAME"

# Run Python script in container
docker exec -i torstream-app python3 << EOF
import asyncio
import sys
sys.path.insert(0, '/app')

from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models.user import User
from app.services.security import hash_password
from datetime import datetime, timezone, timedelta
import uuid

async def create_admin():
    async with AsyncSessionLocal() as session:
        # Check if admin exists
        from sqlalchemy import select
        result = await session.execute(
            select(User).where(User.username == "$ADMIN_USERNAME")
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"User '$ADMIN_USERNAME' already exists")
            return
        
        # Create admin user
        admin = User(
            id=uuid.uuid4(),
            username="$ADMIN_USERNAME",
            password_hash=hash_password("$ADMIN_PASSWORD"),
            is_admin=True,
            is_superadmin=True,
            is_premium=True,
            premium_expires_at=datetime.now(timezone.utc) + timedelta(days=3650),
            created_at=datetime.now(timezone.utc)
        )
        
        session.add(admin)
        await session.commit()
        print(f"Admin user created: $ADMIN_USERNAME")

asyncio.run(create_admin())
EOF

echo ""
echo "=========================================="
echo "Admin Credentials (SAVE THESE!)"
echo "=========================================="
echo "Username: $ADMIN_USERNAME"
echo "Password: $ADMIN_PASSWORD"
echo "=========================================="
echo ""
echo "Please change the password after first login!"
