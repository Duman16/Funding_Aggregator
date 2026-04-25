"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- categories ---
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
    )
    op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)
    op.create_index("ix_categories_name", "categories", ["name"], unique=True)

    # --- grants ---
    op.create_table(
        "grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("opportunity_number", sa.String(100), nullable=True),
        sa.Column("agency_name", sa.String(300), nullable=True),
        sa.Column("agency_code", sa.String(50), nullable=True),
        sa.Column("posted_date", sa.Date(), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("amount_min", sa.Numeric(15, 2), nullable=True),
        sa.Column("amount_max", sa.Numeric(15, 2), nullable=True),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        sa.Column("eligibility", sa.Text(), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("external_id", "source", name="uq_grant_external_source"),
    )
    op.create_index("ix_grant_deadline", "grants", ["deadline"])
    op.create_index("ix_grant_status", "grants", ["status"])
    op.create_index("ix_grant_source", "grants", ["source"])
    op.create_index("ix_grant_agency", "grants", ["agency_name"])
    op.create_index(
        "ix_grant_search_vector",
        "grants",
        ["search_vector"],
        postgresql_using="gin",
    )

    # Trigger to auto-update search_vector on insert/update
    op.execute("""
        CREATE OR REPLACE FUNCTION grants_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.agency_name, '')), 'C');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER grants_search_vector_trigger
        BEFORE INSERT OR UPDATE ON grants
        FOR EACH ROW EXECUTE FUNCTION grants_search_vector_update();
    """)

    # updated_at trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER grants_updated_at_trigger
        BEFORE UPDATE ON grants
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)

    # --- grant_categories (M2M) ---
    op.create_table(
        "grant_categories",
        sa.Column(
            "grant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("grants.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # --- scrape_logs ---
    op.create_table(
        "scrape_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("records_collected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS grants_search_vector_trigger ON grants")
    op.execute("DROP TRIGGER IF EXISTS grants_updated_at_trigger ON grants")
    op.execute("DROP FUNCTION IF EXISTS grants_search_vector_update()")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    op.drop_table("grant_categories")
    op.drop_table("scrape_logs")
    op.drop_table("grants")
    op.drop_table("categories")
    op.drop_table("users")
