"""Commerce: plans, customers, subscriptions, payments, webhook ledger,
enterprise licenses.

Stripe is the billing system of record; these tables are the platform's
projection of it, maintained exclusively by verified webhooks (plus the
checkout/portal session creation calls). The webhook ledger makes
at-least-once delivery idempotent. Coupons are Stripe promotion codes applied
at checkout; hosted invoices live in the Stripe billing portal.
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import PortableJSON

SUB_ACTIVE = "active"
SUB_TRIALING = "trialing"
SUB_PAST_DUE = "past_due"
SUB_CANCELED = "canceled"
SUB_INCOMPLETE = "incomplete"
PREMIUM_STATUSES = {SUB_ACTIVE, SUB_TRIALING}


class Plan(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    interval: Mapped[str] = mapped_column(String(10), nullable=False, default="month")
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stripe_price_id: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BillingCustomer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "billing_customers"
    __table_args__ = (UniqueConstraint("user_id", name="uq_billing_customer_user"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stripe_customer_id: Mapped[str] = mapped_column(
        String(120), nullable=False, unique=True, index=True
    )


class Subscription(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("plans.id", ondelete="SET NULL"), nullable=True
    )
    stripe_subscription_id: Mapped[str] = mapped_column(
        String(120), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False,
                                        default=SUB_INCOMPLETE)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                                       default=False)
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Payment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stripe_payment_intent_id: Mapped[str] = mapped_column(
        String(120), nullable=False, unique=True, index=True
    )
    stripe_invoice_id: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # succeeded|failed|refunded
    refunded_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column(String(300), nullable=False, default="")


class WebhookEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Idempotency ledger: a Stripe event id is processed at most once."""

    __tablename__ = "webhook_events"

    stripe_event_id: Mapped[str] = mapped_column(
        String(120), nullable=False, unique=True, index=True
    )
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(PortableJSON, nullable=False)


class EnterpriseLicense(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Org-level entitlement: every member of a licensed organization has
    premium access, independent of personal subscriptions."""

    __tablename__ = "enterprise_licenses"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    seats: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
