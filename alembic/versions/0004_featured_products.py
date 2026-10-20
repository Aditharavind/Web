"""Allow administrators to select homepage featured products."""

import sqlalchemy as sa

from alembic import op

revision = "0004_featured_products"
down_revision = "0003_admin_sessions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "products",
        sa.Column(
            "is_featured",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index("ix_products_is_featured", "products", ["is_featured"])


def downgrade():
    op.drop_index("ix_products_is_featured", table_name="products")
    op.drop_column("products", "is_featured")
