"""Initial CRM schema.

Revision ID: 001_initial
Revises:
Create Date: 2026-02-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Location (tenant root)
    op.create_table(
        "location",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("timezone", sa.String(50), server_default="UTC"),
        sa.Column("ghl_location_id", sa.String(100)),
        sa.Column("ghl_company_id", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_location_slug", "location", ["slug"])

    # Contact
    op.create_table(
        "contact",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("location.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(50)),
        sa.Column("company_name", sa.String(200)),
        sa.Column("address1", sa.String(255)),
        sa.Column("city", sa.String(100)),
        sa.Column("state", sa.String(50)),
        sa.Column("postal_code", sa.String(20)),
        sa.Column("country", sa.String(50)),
        sa.Column("source", sa.String(100)),
        sa.Column("dnd", sa.Boolean, server_default="false"),
        sa.Column("ghl_id", sa.String(100)),
        sa.Column("ghl_location_id", sa.String(100)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_contact_location_id", "contact", ["location_id"])
    op.create_index("ix_contact_email", "contact", ["email"])
    op.create_index("ix_contact_location_email", "contact", ["location_id", "email"])
    op.create_index("ix_contact_ghl_id", "contact", ["ghl_id"])

    # Tag
    op.create_table(
        "tag",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("location.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("ghl_id", sa.String(100)),
        sa.Column("ghl_location_id", sa.String(100)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("location_id", "name", name="uq_tag_location_name"),
    )
    op.create_index("ix_tag_location_id", "tag", ["location_id"])
    op.create_index("ix_tag_ghl_id", "tag", ["ghl_id"])

    # Contact-Tag M2M
    op.create_table(
        "contact_tag",
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contact.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True),
    )

    # Custom Field Definition
    op.create_table(
        "custom_field_definition",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("location.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("field_key", sa.String(200), nullable=False),
        sa.Column("data_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), server_default="contact"),
        sa.Column("options_json", postgresql.JSONB),
        sa.Column("position", sa.Integer, server_default="0"),
        sa.Column("ghl_id", sa.String(100)),
        sa.Column("ghl_location_id", sa.String(100)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cfd_location_id", "custom_field_definition", ["location_id"])
    op.create_index("ix_cfd_field_key", "custom_field_definition", ["field_key"])

    # Custom Field Value
    op.create_table(
        "custom_field_value",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("definition_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("custom_field_definition.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("value_text", sa.Text),
        sa.Column("value_number", sa.Float),
        sa.Column("value_date", sa.String(50)),
        sa.Column("value_bool", sa.Boolean),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("definition_id", "entity_id", name="uq_cfv_def_entity"),
    )
    op.create_index("ix_cfv_definition_id", "custom_field_value", ["definition_id"])
    op.create_index("ix_cfv_entity_id", "custom_field_value", ["entity_id"])

    # Custom Value
    op.create_table(
        "custom_value",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("location.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("value", sa.Text),
        sa.Column("ghl_id", sa.String(100)),
        sa.Column("ghl_location_id", sa.String(100)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_cv_location_id", "custom_value", ["location_id"])

    # Note
    op.create_table(
        "note",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("location.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contact.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_by", sa.String(100)),
        sa.Column("ghl_id", sa.String(100)),
        sa.Column("ghl_location_id", sa.String(100)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_note_contact_id", "note", ["contact_id"])
    op.create_index("ix_note_location_id", "note", ["location_id"])

    # Task
    op.create_table(
        "task",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("location.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contact.id", ondelete="SET NULL")),
        sa.Column("due_date", sa.Date),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("priority", sa.Integer, server_default="0"),
        sa.Column("assigned_to", sa.String(100)),
        sa.Column("ghl_id", sa.String(100)),
        sa.Column("ghl_location_id", sa.String(100)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_task_location_id", "task", ["location_id"])
    op.create_index("ix_task_contact_id", "task", ["contact_id"])

    # Pipeline
    op.create_table(
        "pipeline",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("location.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("ghl_id", sa.String(100)),
        sa.Column("ghl_location_id", sa.String(100)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("location_id", "name", name="uq_pipeline_location_name"),
    )
    op.create_index("ix_pipeline_location_id", "pipeline", ["location_id"])

    # Pipeline Stage
    op.create_table(
        "pipeline_stage",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipeline.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("position", sa.Integer, server_default="0"),
        sa.Column("ghl_id", sa.String(100)),
        sa.Column("ghl_location_id", sa.String(100)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("pipeline_id", "name", name="uq_stage_pipeline_name"),
    )
    op.create_index("ix_stage_pipeline_id", "pipeline_stage", ["pipeline_id"])

    # Opportunity
    op.create_table(
        "opportunity",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("location.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipeline.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipeline_stage.id", ondelete="SET NULL")),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contact.id", ondelete="SET NULL")),
        sa.Column("monetary_value", sa.Float),
        sa.Column("status", sa.String(50), server_default="open"),
        sa.Column("source", sa.String(100)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("ghl_id", sa.String(100)),
        sa.Column("ghl_location_id", sa.String(100)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_opp_location_id", "opportunity", ["location_id"])
    op.create_index("ix_opp_pipeline_id", "opportunity", ["pipeline_id"])
    op.create_index("ix_opp_stage_id", "opportunity", ["stage_id"])
    op.create_index("ix_opp_contact_id", "opportunity", ["contact_id"])

    # Activity
    op.create_table(
        "activity",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("location.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("metadata_json", postgresql.JSONB),
        sa.Column("created_by", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_activity_location_id", "activity", ["location_id"])
    op.create_index("ix_activity_entity_type", "activity", ["entity_type"])
    op.create_index("ix_activity_entity_id", "activity", ["entity_id"])


def downgrade() -> None:
    op.drop_table("activity")
    op.drop_table("opportunity")
    op.drop_table("pipeline_stage")
    op.drop_table("pipeline")
    op.drop_table("task")
    op.drop_table("note")
    op.drop_table("custom_value")
    op.drop_table("custom_field_value")
    op.drop_table("custom_field_definition")
    op.drop_table("contact_tag")
    op.drop_table("tag")
    op.drop_table("contact")
    op.drop_table("location")
