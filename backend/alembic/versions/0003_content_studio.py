"""Content & Creator Studio: catalog, projects, versions; live-pointer
semantics for game_definitions (immutable rows, movable `live` flag).

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-15
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    # ── game_definitions: immutable rows + live pointer ────────
    op.add_column("game_definitions",
                  sa.Column("live", sa.Boolean(), nullable=False,
                            server_default=sa.text("true")))
    op.drop_index("ix_game_definitions_slug", table_name="game_definitions")
    op.create_index("ix_game_definitions_slug", "game_definitions", ["slug"])
    op.create_index("uq_game_definitions_slug_live", "game_definitions", ["slug"],
                    unique=True, postgresql_where=sa.text("live"))

    # ── catalog ────────────────────────────────────────────────
    op.create_table(
        "certifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(120), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_certifications_slug", "certifications", ["slug"], unique=True)

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("certification_id", sa.Uuid(),
                  sa.ForeignKey("certifications.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("certification_id", "slug", name="uq_campaign_slug"),
    )
    op.create_index("ix_campaigns_certification_id", "campaigns", ["certification_id"])

    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("campaign_id", sa.Uuid(),
                  sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("campaign_id", "slug", name="uq_course_slug"),
    )
    op.create_index("ix_courses_campaign_id", "courses", ["campaign_id"])

    op.create_table(
        "content_projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("certification", sa.String(120), nullable=False, server_default=""),
        sa.Column("owner_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("live_version_id", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_content_projects_slug", "content_projects", ["slug"],
                    unique=True)

    op.create_table(
        "content_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(),
                  sa.ForeignKey("content_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("definition", JSONB(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("review_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("project_id", "version_number", name="uq_version_number"),
    )
    op.create_index("ix_content_versions_project_id", "content_versions",
                    ["project_id"])

    # Deferred FK (circular projects ↔ versions dependency).
    op.create_foreign_key(
        "fk_content_projects_live_version", "content_projects", "content_versions",
        ["live_version_id"], ["id"], ondelete="SET NULL",
    )

    op.create_table(
        "missions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(),
                  sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("project_id", sa.Uuid(),
                  sa.ForeignKey("content_projects.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("course_id", "slug", name="uq_mission_slug"),
    )
    op.create_index("ix_missions_course_id", "missions", ["course_id"])


def downgrade() -> None:
    op.drop_table("missions")
    op.drop_constraint("fk_content_projects_live_version", "content_projects",
                       type_="foreignkey")
    op.drop_table("content_versions")
    op.drop_table("content_projects")
    op.drop_table("courses")
    op.drop_table("campaigns")
    op.drop_table("certifications")
    op.drop_index("uq_game_definitions_slug_live", table_name="game_definitions")
    op.drop_index("ix_game_definitions_slug", table_name="game_definitions")
    op.create_index("ix_game_definitions_slug", "game_definitions", ["slug"],
                    unique=True)
    op.drop_column("game_definitions", "live")
