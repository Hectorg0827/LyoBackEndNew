"""Initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2025-05-11 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(uuid.uuid4())),
        sa.Column('email', sa.String(length=255), unique=True, index=True, nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('avatar_url', sa.String(length=255), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('lang', sa.String(length=10), nullable=False, server_default='en-US'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    
    # Create user_follows table for tracking followers
    op.create_table(
        'user_follows',
        sa.Column('follower_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('following_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('follower_id', 'following_id', name='unique_follower_following'),
    )
    
    # Create posts table
    op.create_table(
        'posts',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(uuid.uuid4())),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('media_urls', sa.JSON(), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('likes_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('comments_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('is_draft', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_private', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Index('idx_posts_user_id', 'user_id'),
        sa.Index('idx_posts_created_at', 'created_at')
    )
    
    # Create comments table
    op.create_table(
        'comments',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(uuid.uuid4())),
        sa.Column('post_id', sa.String(length=36), sa.ForeignKey('posts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('parent_id', sa.String(length=36), sa.ForeignKey('comments.id', ondelete='CASCADE'), nullable=True),
        sa.Column('likes_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Index('idx_comments_post_id', 'post_id'),
        sa.Index('idx_comments_user_id', 'user_id'),
        sa.Index('idx_comments_parent_id', 'parent_id')
    )
    
    # Create likes table
    op.create_table(
        'likes',
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('post_id', sa.String(length=36), sa.ForeignKey('posts.id', ondelete='CASCADE'), nullable=True),
        sa.Column('comment_id', sa.String(length=36), sa.ForeignKey('comments.id', ondelete='CASCADE'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('(post_id IS NULL AND comment_id IS NOT NULL) OR (post_id IS NOT NULL AND comment_id IS NULL)', name='check_like_target'),
        sa.UniqueConstraint('user_id', 'post_id', name='unique_user_post_like'),
        sa.UniqueConstraint('user_id', 'comment_id', name='unique_user_comment_like'),
        sa.Index('idx_likes_post_id', 'post_id'),
        sa.Index('idx_likes_comment_id', 'comment_id')
    )
    
    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.String(length=36), primary_key=True, default=lambda: str(uuid.uuid4())),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actor_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('content', sa.JSON(), nullable=False),
        sa.Column('resource_id', sa.String(length=36), nullable=True),
        sa.Column('resource_type', sa.String(length=50), nullable=True),
        sa.Column('is_read', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Index('idx_notifications_user_id', 'user_id'),
        sa.Index('idx_notifications_created_at', 'created_at'),
        sa.Index('idx_notifications_is_read', 'is_read')
    )
    
    # Add vectors extension for full text search if using PostgreSQL
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')


def downgrade() -> None:
    op.drop_table('notifications')
    op.drop_table('likes')
    op.drop_table('comments')
    op.drop_table('posts')
    op.drop_table('user_follows')
    op.drop_table('users')
    
    # Remove extension
    op.execute('DROP EXTENSION IF EXISTS pg_trgm')
