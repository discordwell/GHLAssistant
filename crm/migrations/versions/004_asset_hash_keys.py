"""Harden AssetRef/AssetJob uniqueness for Postgres (hash keys).

Revision ID: 004_asset_hash_keys
Revises: 003_assets
Create Date: 2026-02-09

Problem:
  The original uniqueness constraints indexed large TEXT columns (URLs, data: URIs,
  signed URLs). Postgres btree indexes have a per-row size limit (~2.7KB); large
  URLs can trigger "index row size exceeds btree maximum" failures.

Fix:
  - Add fixed-size sha256 hex columns:
      asset_ref.identity_sha256
      asset_job.url_sha256
  - Backfill for existing rows
  - Deduplicate any accidental duplicates (nullable UNIQUE columns can allow them)
  - Replace the old UNIQUE constraints with hash-based UNIQUE constraints
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "004_asset_hash_keys"
down_revision = "003_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # gen_random_uuid() already implies pgcrypto in earlier migrations; ensure it's present
    # so we can use digest(..., 'sha256') for backfills.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # 1) Add columns (nullable for backfill).
    op.add_column("asset_ref", sa.Column("identity_sha256", sa.String(length=64), nullable=True))
    op.add_column("asset_job", sa.Column("url_sha256", sa.String(length=64), nullable=True))

    # 2) Backfill hashes (normalize NULL to empty string; keep stable separators).
    op.execute(
        r"""
        UPDATE asset_ref
        SET identity_sha256 = encode(
            digest(
                coalesce(entity_type, '') || E'\x1f' ||
                coalesce(entity_id::text, '') || E'\x1f' ||
                coalesce(remote_entity_id, '') || E'\x1f' ||
                coalesce(field_path, '') || E'\x1f' ||
                coalesce(usage, '') || E'\x1f' ||
                coalesce(original_url, ''),
                'sha256'
            ),
            'hex'
        )
        WHERE identity_sha256 IS NULL OR identity_sha256 = '';
        """
    )
    op.execute(
        r"""
        UPDATE asset_job
        SET url_sha256 = encode(digest(coalesce(btrim(url), ''), 'sha256'), 'hex')
        WHERE url_sha256 IS NULL OR url_sha256 = '';
        """
    )

    # 3) Deduplicate any (location_id, identity_sha256) collisions before UNIQUE constraint.
    # If duplicates exist, keep the earliest row (created_at/id order) and remap jobs to it.
    op.execute(
        r"""
        WITH ranked AS (
          SELECT
            id,
            location_id,
            identity_sha256,
            first_value(id) OVER (
              PARTITION BY location_id, identity_sha256
              ORDER BY created_at ASC, id ASC
            ) AS keep_id,
            row_number() OVER (
              PARTITION BY location_id, identity_sha256
              ORDER BY created_at ASC, id ASC
            ) AS rn
          FROM asset_ref
          WHERE identity_sha256 IS NOT NULL AND identity_sha256 <> ''
        )
        UPDATE asset_job j
        SET asset_ref_id = r.keep_id
        FROM ranked r
        WHERE j.asset_ref_id = r.id AND r.rn > 1;
        """
    )
    op.execute(
        r"""
        WITH ranked AS (
          SELECT
            id,
            location_id,
            identity_sha256,
            row_number() OVER (
              PARTITION BY location_id, identity_sha256
              ORDER BY created_at ASC, id ASC
            ) AS rn
          FROM asset_ref
          WHERE identity_sha256 IS NOT NULL AND identity_sha256 <> ''
        )
        DELETE FROM asset_ref
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1);
        """
    )

    # Deduplicate any (location_id, job_type, url_sha256) collisions before UNIQUE constraint.
    op.execute(
        r"""
        WITH ranked AS (
          SELECT
            id,
            location_id,
            job_type,
            url_sha256,
            row_number() OVER (
              PARTITION BY location_id, job_type, url_sha256
              ORDER BY created_at ASC, id ASC
            ) AS rn
          FROM asset_job
          WHERE url_sha256 IS NOT NULL AND url_sha256 <> ''
        )
        DELETE FROM asset_job
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1);
        """
    )

    # 4) Replace constraints.
    op.drop_constraint("uq_asset_ref_identity", "asset_ref", type_="unique")
    op.drop_constraint("uq_asset_job_location_type_url", "asset_job", type_="unique")

    op.alter_column("asset_ref", "identity_sha256", nullable=False)
    op.alter_column("asset_job", "url_sha256", nullable=False)

    op.create_unique_constraint(
        "uq_asset_ref_location_identity_sha256",
        "asset_ref",
        ["location_id", "identity_sha256"],
    )
    op.create_unique_constraint(
        "uq_asset_job_location_type_url_sha256",
        "asset_job",
        ["location_id", "job_type", "url_sha256"],
    )


def downgrade() -> None:
    # Recreate old constraints and drop hash columns.
    op.drop_constraint("uq_asset_job_location_type_url_sha256", "asset_job", type_="unique")
    op.drop_constraint("uq_asset_ref_location_identity_sha256", "asset_ref", type_="unique")

    op.create_unique_constraint(
        "uq_asset_ref_identity",
        "asset_ref",
        [
            "location_id",
            "entity_type",
            "entity_id",
            "remote_entity_id",
            "field_path",
            "usage",
            "original_url",
        ],
    )
    op.create_unique_constraint(
        "uq_asset_job_location_type_url",
        "asset_job",
        ["location_id", "job_type", "url"],
    )

    op.drop_column("asset_job", "url_sha256")
    op.drop_column("asset_ref", "identity_sha256")

