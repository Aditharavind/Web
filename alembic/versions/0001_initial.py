"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-04-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False, unique=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'products',
        sa.Column('id', sa.String(), primary_key=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('specs', sa.Text()),
        sa.Column('tags', sa.String()),
        sa.Column('image', sa.String()),
        sa.Column('images', sa.Text()),
        sa.Column('created_at', sa.DateTime()),
        sa.UniqueConstraint('name', 'category', name='uq_product_name_category')
    )

    op.create_table(
        'visits',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('ip', sa.String(), nullable=False),
        sa.Column('visited_at', sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table('visits')
    op.drop_table('products')
    op.drop_table('categories')
