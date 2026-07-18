"""Commerce: plans, billing customers, subscriptions, payments, webhook
ledger, enterprise licenses. Seeds commerce.manage onto the admin role.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-18
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
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
        "plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="usd"),
        sa.Column("interval", sa.String(10), nullable=False, server_default="month"),
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stripe_price_id", sa.String(120), nullable=False,
                  server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_plans_code", "plans", ["code"], unique=True)

    op.create_table(
        "billing_customers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stripe_customer_id", sa.String(120), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("user_id", name="uq_billing_customer_user"),
    )
    op.create_index("ix_billing_customers_user_id", "billing_customers", ["user_id"])
    op.create_index("ix_billing_customers_stripe_customer_id", "billing_customers",
                    ["stripe_customer_id"], unique=True)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Uuid(),
                  sa.ForeignKey("plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default="incomplete"),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("trial_end", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_stripe_subscription_id", "subscriptions",
                    ["stripe_subscription_id"], unique=True)

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stripe_payment_intent_id", sa.String(120), nullable=False),
        sa.Column("stripe_invoice_id", sa.String(120), nullable=False,
                  server_default=""),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="usd"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("refunded_amount_cents", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("description", sa.String(300), nullable=False, server_default=""),
        *_timestamps(),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_stripe_payment_intent_id", "payments",
                    ["stripe_payment_intent_id"], unique=True)

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("stripe_event_id", sa.String(120), nullable=False),
        sa.Column("type", sa.String(80), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_webhook_events_stripe_event_id", "webhook_events",
                    ["stripe_event_id"], unique=True)

    op.create_table(
        "enterprise_licenses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("seats", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_enterprise_licenses_organization_id", "enterprise_licenses",
                    ["organization_id"])

    _seed_permission()


def _seed_permission() -> None:
    bind = op.get_bind()
    permission_id = uuid.uuid4()
    bind.execute(
        sa.text("INSERT INTO permissions (id, code, description) "
                "VALUES (:id, :code, :description)"),
        {"id": permission_id, "code": "commerce.manage",
         "description": "Manage plans, refunds, and enterprise licenses"},
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
        "(SELECT id FROM permissions WHERE code = 'commerce.manage')"))
    bind.execute(sa.text("DELETE FROM permissions WHERE code = 'commerce.manage'"))
    for table in ("enterprise_licenses", "webhook_events", "payments",
                  "subscriptions", "billing_customers", "plans"):
        op.drop_table(table)
