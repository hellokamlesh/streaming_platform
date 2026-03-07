# ============================================
# TorStream - Admin Service
# ============================================

import uuid
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.video import Video, VideoAccessType
from app.models.payment import Invoice, Purchase, Subscription, PaymentLog
from app.models.admin import AdminAction, SystemConfig
from app.services.security import hash_password
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class AdminService:
    """Admin management service."""
    
    async def log_action(
        self,
        db: AsyncSession,
        admin_id: Optional[uuid.UUID],
        action_type: str,
        description: str,
        target_user_id: Optional[uuid.UUID] = None,
        action_data: dict = None,
        ip_address: Optional[str] = None
    ):
        """Log admin action."""
        action = AdminAction(
            id=uuid.uuid4(),
            admin_id=admin_id,
            target_user_id=target_user_id,
            action_type=action_type,
            action_description=description,
            action_data=action_data or {},
            ip_address=ip_address
        )
        db.add(action)
        await db.commit()
        
        logger.info(f"Admin action logged: {action_type} by {admin_id}")
    
    # ==================== User Management ====================
    
    async def get_users(
        self,
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None
    ) -> List[User]:
        """Get users with optional search."""
        query = select(User)
        
        if search:
            query = query.where(User.username.ilike(f"%{search}%"))
        
        query = query.order_by(desc(User.created_at)).limit(limit).offset(offset)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_user_by_id(
        self,
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> Optional[User]:
        """Get user by ID."""
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def ban_user(
        self,
        db: AsyncSession,
        admin: User,
        user: User,
        reason: str,
        ip_address: Optional[str] = None
    ) -> bool:
        """Ban a user."""
        if user.is_superadmin:
            logger.warning(f"Attempted to ban superadmin: {user.id}")
            return False
        
        user.is_banned = True
        user.ban_reason = reason
        
        await self.log_action(
            db, admin.id, "ban_user",
            f"Banned user {user.username}",
            user.id,
            {"reason": reason},
            ip_address
        )
        
        await db.commit()
        logger.info(f"User banned: {user.username} by {admin.username}")
        return True
    
    async def unban_user(
        self,
        db: AsyncSession,
        admin: User,
        user: User,
        ip_address: Optional[str] = None
    ) -> bool:
        """Unban a user."""
        user.is_banned = False
        user.ban_reason = None
        
        await self.log_action(
            db, admin.id, "unban_user",
            f"Unbanned user {user.username}",
            user.id,
            ip_address=ip_address
        )
        
        await db.commit()
        logger.info(f"User unbanned: {user.username} by {admin.username}")
        return True
    
    async def grant_premium(
        self,
        db: AsyncSession,
        admin: User,
        user: User,
        days: int,
        ip_address: Optional[str] = None
    ) -> bool:
        """Grant premium to user for specified days."""
        now = datetime.now(timezone.utc)
        
        # Extend existing premium if active
        if user.is_premium and user.premium_expires_at and user.premium_expires_at > now:
            user.premium_expires_at = user.premium_expires_at + timedelta(days=days)
        else:
            user.is_premium = True
            user.premium_expires_at = now + timedelta(days=days)
        
        await self.log_action(
            db, admin.id, "grant_premium",
            f"Granted {days} days premium to {user.username}",
            user.id,
            {"days": days, "expires_at": user.premium_expires_at.isoformat()},
            ip_address
        )
        
        await db.commit()
        logger.info(f"Premium granted to {user.username} for {days} days")
        return True
    
    async def revoke_premium(
        self,
        db: AsyncSession,
        admin: User,
        user: User,
        ip_address: Optional[str] = None
    ) -> bool:
        """Revoke user's premium."""
        user.is_premium = False
        user.premium_expires_at = None
        
        await self.log_action(
            db, admin.id, "revoke_premium",
            f"Revoked premium from {user.username}",
            user.id,
            ip_address=ip_address
        )
        
        await db.commit()
        logger.info(f"Premium revoked from {user.username}")
        return True
    
    async def create_admin(
        self,
        db: AsyncSession,
        superadmin: User,
        username: str,
        password: str,
        ip_address: Optional[str] = None
    ) -> Optional[User]:
        """Create new admin user (superadmin only)."""
        if not superadmin.is_superadmin:
            return None
        
        # Check if username exists
        existing = await db.execute(
            select(User).where(User.username == username)
        )
        if existing.scalar_one_or_none():
            return None
        
        user = User(
            id=uuid.uuid4(),
            username=username,
            password_hash=hash_password(password),
            is_admin=True,
            is_superadmin=False,
            is_premium=True,
            premium_expires_at=datetime.now(timezone.utc) + timedelta(days=3650)  # 10 years
        )
        
        db.add(user)
        
        await self.log_action(
            db, superadmin.id, "create_admin",
            f"Created admin user: {username}",
            user.id,
            ip_address=ip_address
        )
        
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"Admin created: {username} by {superadmin.username}")
        return user
    
    # ==================== Video Management ====================
    
    async def get_all_videos(
        self,
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0,
        include_inactive: bool = True
    ) -> List[Video]:
        """Get all videos for admin."""
        query = select(Video)
        
        if not include_inactive:
            query = query.where(Video.is_active == True)
        
        query = query.order_by(desc(Video.created_at)).limit(limit).offset(offset)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def toggle_video_active(
        self,
        db: AsyncSession,
        admin: User,
        video: Video,
        ip_address: Optional[str] = None
    ) -> bool:
        """Toggle video active status."""
        video.is_active = not video.is_active
        
        await self.log_action(
            db, admin.id, "toggle_video",
            f"Set video {video.title} active={video.is_active}",
            video.uploaded_by,
            {"video_id": str(video.id), "active": video.is_active},
            ip_address
        )
        
        await db.commit()
        return True
    
    async def delete_video(
        self,
        db: AsyncSession,
        admin: User,
        video: Video,
        ip_address: Optional[str] = None
    ) -> bool:
        """Delete video (superadmin only)."""
        if not admin.is_superadmin:
            return False
        
        from app.videos.service import video_service
        
        success = await video_service.delete_video(db, video)
        
        if success:
            await self.log_action(
                db, admin.id, "delete_video",
                f"Deleted video: {video.title}",
                video.uploaded_by,
                {"video_id": str(video.id)},
                ip_address
            )
        
        return success
    
    # ==================== Payment Management ====================
    
    async def get_pending_payments(
        self,
        db: AsyncSession,
        limit: int = 50
    ) -> List[Invoice]:
        """Get pending payments."""
        result = await db.execute(
            select(Invoice)
            .where(Invoice.status == "Pending")
            .order_by(desc(Invoice.created_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def approve_payment(
        self,
        db: AsyncSession,
        admin: User,
        invoice: Invoice,
        ip_address: Optional[str] = None
    ) -> bool:
        """Manually approve a payment."""
        from app.payments.service import payment_service
        
        if invoice.status.value != "Pending":
            return False
        
        invoice.status = "Settled"
        
        success = await payment_service._process_settled_invoice(db, invoice)
        
        if success:
            invoice.is_processed = True
            invoice.processed_at = datetime.now(timezone.utc)
            
            await self.log_action(
                db, admin.id, "approve_payment",
                f"Manually approved payment {invoice.id}",
                invoice.user_id,
                {"invoice_id": str(invoice.id), "amount": float(invoice.amount_usd)},
                ip_address
            )
            
            await db.commit()
        
        return success
    
    async def get_purchases(
        self,
        db: AsyncSession,
        limit: int = 50
    ) -> List[Purchase]:
        """Get all purchases."""
        result = await db.execute(
            select(Purchase)
            .order_by(desc(Purchase.purchased_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    # ==================== System Configuration ====================
    
    async def get_system_config(
        self,
        db: AsyncSession
    ) -> List[SystemConfig]:
        """Get all system configuration."""
        result = await db.execute(
            select(SystemConfig).order_by(SystemConfig.key)
        )
        return result.scalars().all()
    
    async def update_config(
        self,
        db: AsyncSession,
        admin: User,
        key: str,
        value: str,
        ip_address: Optional[str] = None
    ) -> bool:
        """Update system configuration."""
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )
        config = result.scalar_one_or_none()
        
        if not config or not config.is_editable:
            return False
        
        old_value = config.value
        config.value = value
        config.updated_by = admin.id
        config.updated_at = datetime.now(timezone.utc)
        
        await self.log_action(
            db, admin.id, "update_config",
            f"Updated config {key}",
            None,
            {"key": key, "old_value": old_value, "new_value": value},
            ip_address
        )
        
        await db.commit()
        return True
    
    async def get_config_value(
        self,
        db: AsyncSession,
        key: str,
        default=None
    ):
        """Get configuration value."""
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )
        config = result.scalar_one_or_none()
        
        if not config:
            return default
        
        # Convert to appropriate type
        if config.value_type == "bool":
            return config.value.lower() == "true"
        elif config.value_type == "int":
            return int(config.value)
        elif config.value_type == "decimal":
            return Decimal(config.value)
        
        return config.value
    
    # ==================== Statistics ====================
    
    async def get_statistics(self, db: AsyncSession) -> dict:
        """Get platform statistics."""
        # User counts
        total_users = await db.scalar(select(func.count(User.id)))
        premium_users = await db.scalar(
            select(func.count(User.id)).where(User.is_premium == True)
        )
        banned_users = await db.scalar(
            select(func.count(User.id)).where(User.is_banned == True)
        )
        
        # Video counts
        total_videos = await db.scalar(select(func.count(Video.id)))
        active_videos = await db.scalar(
            select(func.count(Video.id)).where(Video.is_active == True)
        )
        
        # Payment totals
        total_revenue = await db.scalar(
            select(func.sum(Invoice.amount_usd))
            .where(Invoice.status == "Settled")
        ) or 0
        
        pending_payments = await db.scalar(
            select(func.count(Invoice.id))
            .where(Invoice.status == "Pending")
        )
        
        return {
            "users": {
                "total": total_users,
                "premium": premium_users,
                "banned": banned_users,
            },
            "videos": {
                "total": total_videos,
                "active": active_videos,
            },
            "payments": {
                "total_revenue": float(total_revenue),
                "pending": pending_payments,
            }
        }
    
    # ==================== Admin Actions Log ====================
    
    async def get_admin_logs(
        self,
        db: AsyncSession,
        limit: int = 100,
        action_type: Optional[str] = None
    ) -> List[AdminAction]:
        """Get admin action logs."""
        query = select(AdminAction)
        
        if action_type:
            query = query.where(AdminAction.action_type == action_type)
        
        query = query.order_by(desc(AdminAction.created_at)).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()


# Global admin service instance
admin_service = AdminService()
