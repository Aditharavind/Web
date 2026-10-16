"""Store revocable admin sessions without persisting bearer tokens."""

import sqlalchemy as sa

from alembic import op

revision = "0003_admin_sessions"
down_revision = "0002_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"])


def downgrade():
    op.drop_table("admin_sessions")
