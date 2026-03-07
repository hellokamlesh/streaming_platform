"""Add thumbnail control features (blur/placeholder).

Revision ID: 0002_thumbnail_controls
Revises: 0001_initial
Create Date: 2025-03-05 17:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002_thumbnail_controls'
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Placeholder columns
    op.add_column('videos', sa.Column('is_placeholder', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('videos', sa.Column('placeholder_message', sa.String(length=255), nullable=True, server_default='Coming Soon'))
    op.add_column('videos', sa.Column('placeholder_image', sa.String(length=255), nullable=True))
    op.add_column('videos', sa.Column('fake_duration_seconds', sa.Integer(), nullable=True))
    
    # Blur columns
    op.add_column('videos', sa.Column('blur_level', sa.String(length=20), nullable=False, server_default='none'))
    op.add_column('videos', sa.Column('blur_until_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('videos', sa.Column('custom_blur_image', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('videos', 'custom_blur_image')
    op.drop_column('videos', 'blur_until_date')
    op.drop_column('videos', 'blur_level')
    op.drop_column('videos', 'fake_duration_seconds')
    op.drop_column('videos', 'placeholder_image')
    op.drop_column('videos', 'placeholder_message')
    op.drop_column('videos', 'is_placeholder')

