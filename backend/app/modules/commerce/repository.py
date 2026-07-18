import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.modules.commerce.models import (
    BillingCustomer,
    EnterpriseLicense,
    Payment,
    Plan,
    Subscription,
    WebhookEvent,
)
from app.repositories.base import BaseRepository


class PlanRepository(BaseRepository[Plan]):
    model = Plan

    async def get_by_code(self, code: str) -> Plan | None:
        stmt = self._base_query().where(Plan.code == code)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_active(self) -> list[Plan]:
        stmt = self._base_query().where(Plan.active.is_(True)).order_by(Plan.price_cents)
        return list((await self.session.execute(stmt)).scalars())


class BillingCustomerRepository(BaseRepository[BillingCustomer]):
    model = BillingCustomer

    async def get_for_user(self, user_id: uuid.UUID) -> BillingCustomer | None:
        stmt = select(BillingCustomer).where(BillingCustomer.user_id == user_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_stripe_id(self, stripe_customer_id: str) -> BillingCustomer | None:
        stmt = select(BillingCustomer).where(
            BillingCustomer.stripe_customer_id == stripe_customer_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class SubscriptionRepository(BaseRepository[Subscription]):
    model = Subscription

    async def get_by_stripe_id(self, stripe_subscription_id: str) -> Subscription | None:
        stmt = select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_subscription_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def latest_for_user(self, user_id: uuid.UUID) -> Subscription | None:
        stmt = (select(Subscription)
                .where(Subscription.user_id == user_id)
                .order_by(Subscription.created_at.desc())
                .limit(1))
        return (await self.session.execute(stmt)).scalar_one_or_none()


class PaymentRepository(BaseRepository[Payment]):
    model = Payment

    async def get_by_intent(self, payment_intent_id: str) -> Payment | None:
        stmt = select(Payment).where(
            Payment.stripe_payment_intent_id == payment_intent_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Payment]:
        stmt = (select(Payment)
                .where(Payment.user_id == user_id)
                .order_by(Payment.created_at.desc()))
        return list((await self.session.execute(stmt)).scalars())


class WebhookEventRepository(BaseRepository[WebhookEvent]):
    model = WebhookEvent

    async def seen(self, stripe_event_id: str) -> bool:
        stmt = select(WebhookEvent.id).where(
            WebhookEvent.stripe_event_id == stripe_event_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None


class EnterpriseLicenseRepository(BaseRepository[EnterpriseLicense]):
    model = EnterpriseLicense

    async def active_for_organizations(
        self, organization_ids: list[uuid.UUID]
    ) -> EnterpriseLicense | None:
        if not organization_ids:
            return None
        now = datetime.now(UTC)
        stmt = self._base_query().where(
            EnterpriseLicense.organization_id.in_(organization_ids),
            EnterpriseLicense.status == "active",
        )
        for license_ in (await self.session.execute(stmt)).scalars():
            expires = license_.expires_at
            if expires is not None and expires.tzinfo is None:  # SQLite naive
                expires = expires.replace(tzinfo=UTC)
            if expires is None or expires > now:
                return license_
        return None
