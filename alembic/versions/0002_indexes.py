"""Align migration indexes with the SQLAlchemy models."""
from alembic import op

revision = "0002_indexes"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

INDEXES = (
    ("categories", "id"),
    ("products", "id"),
    ("products", "category"),
    ("products", "category_id"),
    ("visits", "id"),
    ("visits", "ip"),
    ("visits", "visited_at"),
)


def upgrade():
    for table, column in INDEXES:
        op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table, column in reversed(INDEXES):
        op.drop_index(f"ix_{table}_{column}", table_name=table)
