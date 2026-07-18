"""AI service: request/response audit trail and durable response cache.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-16
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
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
        "ai_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("input", JSONB(), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("personalized", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_ai_requests_user_id", "ai_requests", ["user_id"])
    op.create_index("ix_ai_requests_feature", "ai_requests", ["feature"])
    op.create_index("ix_ai_requests_hash_status", "ai_requests",
                    ["prompt_hash", "status"])

    op.create_table(
        "ai_responses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_id", sa.Uuid(),
                  sa.ForeignKey("ai_requests.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tokens_input", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_output", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        *_timestamps(),
    )
    op.create_index("ix_ai_responses_request_id", "ai_responses", ["request_id"],
                    unique=True)


def downgrade() -> None:
    op.drop_table("ai_responses")
    op.drop_table("ai_requests")
