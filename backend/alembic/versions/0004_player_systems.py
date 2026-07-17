"""Player systems: XP ledger + aggregate, achievements, mission progress,
daily streaks, cross-session inventory. Seeds the achievements.manage
permission onto the admin role.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-15
"""
import uuid

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
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
        "player_xp",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("total_xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        *_timestamps(),
        sa.UniqueConstraint("user_id", name="uq_player_xp_user"),
    )
    op.create_index("ix_player_xp_user_id", "player_xp", ["user_id"])
    # leaderboard scan
    op.create_index("ix_player_xp_total", "player_xp", [sa.text("total_xp DESC")])

    op.create_table(
        "xp_transactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False, server_default=""),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_xp_transactions_user_id", "xp_transactions", ["user_id"])

    op.create_table(
        "achievements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("icon", sa.String(200), nullable=False, server_default=""),
        sa.Column("xp_reward", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hidden", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        *_timestamps(),
    )
    op.create_index("ix_achievements_code", "achievements", ["code"], unique=True)

    op.create_table(
        "user_achievements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("achievement_id", sa.Uuid(),
                  sa.ForeignKey("achievements.id", ondelete="CASCADE"),
                  nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )
    op.create_index("ix_user_achievements_user_id", "user_achievements", ["user_id"])
    op.create_index("ix_user_achievements_achievement_id", "user_achievements",
                    ["achievement_id"])

    op.create_table(
        "mission_progress",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default="in_progress"),
        sa.Column("completions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_ending", sa.String(120)),
        sa.Column("questions_answered", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("questions_correct", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("last_played_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "slug", name="uq_progress_user_slug"),
    )
    op.create_index("ix_mission_progress_user_id", "mission_progress", ["user_id"])
    op.create_index("ix_mission_progress_slug", "mission_progress", ["slug"])

    op.create_table(
        "player_streaks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("longest_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_activity_date", sa.Date()),
        *_timestamps(),
        sa.UniqueConstraint("user_id", name="uq_streak_user"),
    )
    op.create_index("ix_player_streaks_user_id", "player_streaks", ["user_id"])

    op.create_table(
        "player_inventory",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_slug", sa.String(200), nullable=False, server_default=""),
        sa.Column("item_key", sa.String(200), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "source_slug", "item_key",
                            name="uq_inventory_item"),
    )
    op.create_index("ix_player_inventory_user_id", "player_inventory", ["user_id"])

    _seed_permission()


def _seed_permission() -> None:
    bind = op.get_bind()
    permission_id = uuid.uuid4()
    bind.execute(
        sa.text("INSERT INTO permissions (id, code, description) "
                "VALUES (:id, :code, :description)"),
        {"id": permission_id, "code": "achievements.manage",
         "description": "Define and manage the achievement catalog"},
    )
    admin_role_id = bind.execute(
        sa.text("SELECT id FROM roles WHERE name = 'admin'")
    ).scalar_one_or_none()
    if admin_role_id is not None:
        bind.execute(
            sa.text("INSERT INTO role_permissions (id, role_id, permission_id) "
                    "VALUES (:id, :role_id, :permission_id)"),
            {"id": uuid.uuid4(), "role_id": admin_role_id,
             "permission_id": permission_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'achievements.manage')"))
    bind.execute(sa.text("DELETE FROM permissions WHERE code = 'achievements.manage'"))
    for table in ("player_inventory", "player_streaks", "mission_progress",
                  "user_achievements", "achievements", "xp_transactions",
                  "player_xp"):
        op.drop_table(table)
