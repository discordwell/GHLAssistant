"""Add raw GHL entity preservation table.

Revision ID: 002_ghl_raw_entity
Revises: 001_initial
Create Date: 2026-02-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_ghl_raw_entity"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ghl_raw_entity",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("location.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("ghl_id", sa.String(100), nullable=False),
        sa.Column("ghl_location_id", sa.String(100)),
        sa.Column("payload_json", postgresql.JSONB, nullable=False),
        sa.Column("source", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("location_id", "entity_type", "ghl_id", name="uq_raw_location_type_id"),
    )
    op.create_index("ix_raw_location_id", "ghl_raw_entity", ["location_id"])
    op.create_index("ix_raw_entity_type", "ghl_raw_entity", ["entity_type"])
    op.create_index("ix_raw_ghl_id", "ghl_raw_entity", ["ghl_id"])


def downgrade() -> None:
    op.drop_table("ghl_raw_entity")

