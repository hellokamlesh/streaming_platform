"""Initial migration - create all tables

Revision ID: 0001_initial
Revises: 
Create Date: 2024-02-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('username', sa.String(length=32), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False),
        sa.Column('is_superadmin', sa.Boolean(), nullable=False),
        sa.Column('is_premium', sa.Boolean(), nullable=False),
        sa.Column('premium_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_banned', sa.Boolean(), nullable=False),
        sa.Column('ban_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    
    # Create user_sessions table
    op.create_table('user_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_token', sa.String(length=255), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_active', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_token')
    )
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)
    op.create_index('ix_user_sessions_user_id_created_at', 'user_sessions', ['user_id', 'created_at'], unique=False)
    
    # Create failed_login_attempts table
    op.create_table('failed_login_attempts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('username', sa.String(length=32), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('attempted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reason', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_failed_login_attempts_username'), 'failed_login_attempts', ['username'], unique=False)
    op.create_index(op.f('ix_failed_login_attempts_ip_address'), 'failed_login_attempts', ['ip_address'], unique=False)
    op.create_index('ix_failed_login_ip_time', 'failed_login_attempts', ['ip_address', 'attempted_at'], unique=False)
    op.create_index('ix_failed_login_username_time', 'failed_login_attempts', ['username', 'attempted_at'], unique=False)
    
    # Create videos table
    op.create_table('videos',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('access_type', sa.Enum('FREE', 'PPV', 'PREMIUM', name='videoaccesstype'), nullable=False),
        sa.Column('ppv_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('thumbnail_filename', sa.String(length=255), nullable=True),
        sa.Column('preview_filename', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_processing', sa.Boolean(), nullable=False),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('view_count', sa.Integer(), nullable=False),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('filename')
    )
    op.create_index(op.f('ix_videos_uploaded_by'), 'videos', ['uploaded_by'], unique=False)
    op.create_index('ix_videos_access_type_active', 'videos', ['access_type', 'is_active'], unique=False)
    op.create_index(op.f('ix_videos_created_at'), 'videos', ['created_at'], unique=False)
    
    # Create invoices table
    op.create_table('invoices',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('btcpay_invoice_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_type', sa.Enum('PPV', 'SUBSCRIPTION_MONTHLY', 'SUBSCRIPTION_YEARLY', name='invoicetype'), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('amount_usd', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('amount_btc', sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'SETTLED', 'EXPIRED', 'INVALID', name='invoicestatus'), nullable=False),
        sa.Column('is_processed', sa.Boolean(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('btcpay_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('btcpay_invoice_id')
    )
    op.create_index(op.f('ix_invoices_user_id'), 'invoices', ['user_id'], unique=False)
    op.create_index(op.f('ix_invoices_video_id'), 'invoices', ['video_id'], unique=False)
    op.create_index(op.f('ix_invoices_status'), 'invoices', ['status'], unique=False)
    op.create_index('ix_invoices_user_status', 'invoices', ['user_id', 'status'], unique=False)
    op.create_index(op.f('ix_invoices_created_at'), 'invoices', ['created_at'], unique=False)
    op.create_index('ix_invoices_status_processed', 'invoices', ['status', 'is_processed'], unique=False)
    
    # Create purchases table
    op.create_table('purchases',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('price_paid', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('purchased_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_refunded', sa.Boolean(), nullable=False),
        sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('refund_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchases_user_id'), 'purchases', ['user_id'], unique=False)
    op.create_index(op.f('ix_purchases_video_id'), 'purchases', ['video_id'], unique=False)
    op.create_index(op.f('ix_purchases_invoice_id'), 'purchases', ['invoice_id'], unique=False)
    op.create_index('ix_purchases_user_video', 'purchases', ['user_id', 'video_id'], unique=True)
    op.create_index(op.f('ix_purchases_purchased_at'), 'purchases', ['purchased_at'], unique=False)
    
    # Create video_access table
    op.create_table('video_access',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('access_type', sa.String(length=20), nullable=False),
        sa.Column('purchase_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('granted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['purchase_id'], ['purchases.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_video_access_user_id'), 'video_access', ['user_id'], unique=False)
    op.create_index(op.f('ix_video_access_video_id'), 'video_access', ['video_id'], unique=False)
    op.create_index('ix_video_access_user_video', 'video_access', ['user_id', 'video_id'], unique=True)
    op.create_index(op.f('ix_video_access_granted_at'), 'video_access', ['granted_at'], unique=False)
    
    # Create subscriptions table
    op.create_table('subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('subscription_type', sa.String(length=20), nullable=False),
        sa.Column('price_paid', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_cancelled', sa.Boolean(), nullable=False),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('auto_renew', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subscriptions_user_id'), 'subscriptions', ['user_id'], unique=False)
    op.create_index(op.f('ix_subscriptions_invoice_id'), 'subscriptions', ['invoice_id'], unique=False)
    op.create_index('ix_subscriptions_user_active', 'subscriptions', ['user_id', 'is_active'], unique=False)
    op.create_index(op.f('ix_subscriptions_expires_at'), 'subscriptions', ['expires_at'], unique=False)
    
    # Create payment_logs table
    op.create_table('payment_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payment_logs_invoice_id'), 'payment_logs', ['invoice_id'], unique=False)
    op.create_index(op.f('ix_payment_logs_event_type'), 'payment_logs', ['event_type'], unique=False)
    op.create_index('ix_payment_logs_invoice_event', 'payment_logs', ['invoice_id', 'event_type'], unique=False)
    op.create_index(op.f('ix_payment_logs_created_at'), 'payment_logs', ['created_at'], unique=False)
    
    # Create admin_actions table
    op.create_table('admin_actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('admin_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('target_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('action_description', sa.Text(), nullable=False),
        sa.Column('action_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['target_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_actions_admin_id'), 'admin_actions', ['admin_id'], unique=False)
    op.create_index(op.f('ix_admin_actions_target_user_id'), 'admin_actions', ['target_user_id'], unique=False)
    op.create_index(op.f('ix_admin_actions_action_type'), 'admin_actions', ['action_type'], unique=False)
    op.create_index('ix_admin_actions_admin_time', 'admin_actions', ['admin_id', 'created_at'], unique=False)
    op.create_index('ix_admin_actions_type_time', 'admin_actions', ['action_type', 'created_at'], unique=False)
    
    # Create system_config table
    op.create_table('system_config',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('value_type', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_editable', sa.Boolean(), nullable=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    op.create_index(op.f('ix_system_config_key'), 'system_config', ['key'], unique=True)
    
    # Insert default system config
    op.execute("""
        INSERT INTO system_config (id, key, value, value_type, description, is_editable, created_at, updated_at)
        VALUES 
            (gen_random_uuid(), 'registration_enabled', 'true', 'bool', 'Allow new user registrations', true, NOW(), NOW()),
            (gen_random_uuid(), 'uploads_enabled', 'true', 'bool', 'Allow video uploads', true, NOW(), NOW()),
            (gen_random_uuid(), 'maintenance_mode', 'false', 'bool', 'Enable maintenance mode', true, NOW(), NOW()),
            (gen_random_uuid(), 'default_ppv_price', '4.99', 'decimal', 'Default PPV price in USD', true, NOW(), NOW()),
            (gen_random_uuid(), 'premium_monthly_price', '9.99', 'decimal', 'Monthly premium price in USD', true, NOW(), NOW()),
            (gen_random_uuid(), 'premium_yearly_price', '99.99', 'decimal', 'Yearly premium price in USD', true, NOW(), NOW()),
            (gen_random_uuid(), 'max_upload_size_mb', '5120', 'int', 'Maximum upload size in MB', true, NOW(), NOW()),
            (gen_random_uuid(), 'require_captcha', 'true', 'bool', 'Require captcha for registration', true, NOW(), NOW())
    """)


def downgrade() -> None:
    op.drop_table('system_config')
    op.drop_table('admin_actions')
    op.drop_table('payment_logs')
    op.drop_table('subscriptions')
    op.drop_table('video_access')
    op.drop_table('purchases')
    op.drop_table('invoices')
    op.drop_table('videos')
    op.drop_table('failed_login_attempts')
    op.drop_table('user_sessions')
    op.drop_table('users')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS videoaccesstype')
    op.execute('DROP TYPE IF EXISTS invoicetype')
    op.execute('DROP TYPE IF EXISTS invoicestatus')
