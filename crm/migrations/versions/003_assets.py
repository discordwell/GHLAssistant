"""Add canonical asset store + references + job queue.

Revision ID: 003_assets
Revises: 002_ghl_raw_entity
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_assets"
down_revision = "002_ghl_raw_entity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset",
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
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("content_type", sa.String(200)),
        sa.Column("original_filename", sa.String(500)),
        sa.Column("original_url", sa.Text),
        sa.Column("source", sa.String(50)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("meta_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("location_id", "sha256", name="uq_asset_location_sha256"),
    )
    op.create_index("ix_asset_location_id", "asset", ["location_id"])
    op.create_index("ix_asset_sha256", "asset", ["sha256"])
    op.create_index("ix_asset_location_sha256", "asset", ["location_id", "sha256"])

    op.create_table(
        "asset_ref",
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
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("asset.id", ondelete="SET NULL"),
        ),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("remote_entity_id", sa.String(200)),
        sa.Column("field_path", sa.String(500)),
        sa.Column("usage", sa.String(50)),
        sa.Column("original_url", sa.Text),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("meta_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "location_id",
            "entity_type",
            "entity_id",
            "remote_entity_id",
            "field_path",
            "usage",
            "original_url",
            name="uq_asset_ref_identity",
        ),
    )
    op.create_index("ix_asset_ref_location_id", "asset_ref", ["location_id"])
    op.create_index("ix_asset_ref_asset_id", "asset_ref", ["asset_id"])
    op.create_index("ix_asset_ref_entity_type", "asset_ref", ["entity_type"])
    op.create_index("ix_asset_ref_entity_id", "asset_ref", ["entity_id"])
    op.create_index("ix_asset_ref_remote_entity_id", "asset_ref", ["remote_entity_id"])
    op.create_index("ix_asset_ref_location_entity", "asset_ref", ["location_id", "entity_type"])

    op.create_table(
        "asset_remote_map",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("asset.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_system", sa.String(50), nullable=False, server_default="ghl"),
        sa.Column(
            "target_location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("location.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("remote_id", sa.String(200)),
        sa.Column("remote_url", sa.Text),
        sa.Column("uploaded_at", sa.DateTime(timezone=True)),
        sa.Column("meta_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "asset_id",
            "target_system",
            "target_location_id",
            name="uq_asset_remote_map_asset_target",
        ),
    )
    op.create_index("ix_asset_remote_map_asset", "asset_remote_map", ["asset_id"])
    op.create_index("ix_asset_remote_map_target_location", "asset_remote_map", ["target_location_id"])

    op.create_table(
        "asset_job",
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
        sa.Column("job_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "asset_ref_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("asset_ref.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("asset.id", ondelete="SET NULL"),
        ),
        sa.Column("url", sa.Text),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="5"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("locked_by", sa.String(200)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text),
        sa.Column("meta_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("location_id", "job_type", "url", name="uq_asset_job_location_type_url"),
    )
    op.create_index("ix_asset_job_location_id", "asset_job", ["location_id"])
    op.create_index("ix_asset_job_job_type", "asset_job", ["job_type"])
    op.create_index("ix_asset_job_status", "asset_job", ["status"])
    op.create_index("ix_asset_job_next_attempt_at", "asset_job", ["next_attempt_at"])
    op.create_index("ix_asset_job_asset_ref_id", "asset_job", ["asset_ref_id"])
    op.create_index("ix_asset_job_asset_id", "asset_job", ["asset_id"])
    op.create_index("ix_asset_job_status_next", "asset_job", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_table("asset_job")
    op.drop_table("asset_remote_map")
    op.drop_table("asset_ref")
    op.drop_table("asset")
