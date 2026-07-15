"""Game Runtime: published definitions, sessions, save points.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-15
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
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
    op.create_table(
        "game_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("certification", sa.String(120), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="published"),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("definition", JSONB(), nullable=False),
        sa.Column("published_by", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_game_definitions_slug", "game_definitions", ["slug"], unique=True)
    op.create_index("ix_game_definitions_certification", "game_definitions",
                    ["certification"])

    op.create_table(
        "game_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("definition_id", sa.Uuid(),
                  sa.ForeignKey("game_definitions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("state", JSONB(), nullable=False),
        sa.Column("ending_id", sa.String(120)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *_timestamps(),
    )
    op.create_index("ix_game_sessions_user_id", "game_sessions", ["user_id"])
    op.create_index("ix_game_sessions_definition_id", "game_sessions", ["definition_id"])
    # hot lookup: the player's active run of a given game
    op.create_index("ix_game_sessions_user_definition_status", "game_sessions",
                    ["user_id", "definition_id", "status"])

    op.create_table(
        "save_points",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(),
                  sa.ForeignKey("game_sessions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("state", JSONB(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_save_points_session_id", "save_points", ["session_id"])


def downgrade() -> None:
    op.drop_table("save_points")
    op.drop_table("game_sessions")
    op.drop_table("game_definitions")
