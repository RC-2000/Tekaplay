"""Commerce orchestration.

Read path: entitlement = an active/trialing personal subscription OR an
active enterprise license on any organization the user belongs to.
Write path: local state is mutated only by verified, idempotent webhooks —
checkout and portal calls create Stripe sessions but never guess outcomes.
"""
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.errors import NotFoundError, ValidationFailedError
from app.core.logging import get_logger
from app.events.bus import DomainEvent, EventBus
from app.modules.commerce import events as ev
from app.modules.commerce.gateway import PaymentGateway
from app.modules.commerce.models import (
    PREMIUM_STATUSES,
    SUB_CANCELED,
    SUB_INCOMPLETE,
    SUB_PAST_DUE,
    BillingCustomer,
    EnterpriseLicense,
    Payment,
    Plan,
    Subscription,
    WebhookEvent,
)
from app.modules.commerce.repository import (
    BillingCustomerRepository,
    EnterpriseLicenseRepository,
    PaymentRepository,
    PlanRepository,
    SubscriptionRepository,
    WebhookEventRepository,
)
from app.modules.users.audit import AuditService
from app.modules.users.service import UserService
from app.services.base import BaseService

log = get_logger(__name__)


def _from_unix(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), UTC)
    except (TypeError, ValueError):
        return None


class CommerceService(BaseService):
    def __init__(
        self,
        plans: PlanRepository,
        customers: BillingCustomerRepository,
        subscriptions: SubscriptionRepository,
        payments: PaymentRepository,
        webhooks: WebhookEventRepository,
        licenses: EnterpriseLicenseRepository,
        gateway: PaymentGateway,
        users: UserService,
        audit: AuditService,
        event_bus: EventBus,
    ) -> None:
        super().__init__(event_bus)
        self._plans = plans
        self._customers = customers
        self._subscriptions = subscriptions
        self._payments = payments
        self._webhooks = webhooks
        self._licenses = licenses
        self._gateway = gateway
        self._users = users
        self._audit = audit

    # ── Plans ──────────────────────────────────────────────────
    async def list_plans(self) -> list[Plan]:
        return await self._plans.list_active()

    async def create_plan(self, data: dict[str, Any], actor: uuid.UUID) -> Plan:
        if await self._plans.get_by_code(data["code"]) is not None:
            raise ValidationFailedError("A plan with this code already exists",
                                        details={"code": data["code"]})
        plan = Plan(**data)
        self._plans.add(plan)
        await self._plans.flush()
        self._audit.record(action="commerce.plan_created", actor_user_id=actor,
                           entity_type="plan", entity_id=plan.id,
                           meta={"code": plan.code})
        return plan

    # ── Checkout & portal ──────────────────────────────────────
    async def start_checkout(self, *, user_id: uuid.UUID, email: str,
                             plan_code: str, success_url: str,
                             cancel_url: str) -> str:
        plan = await self._plans.get_by_code(plan_code)
        if plan is None or not plan.active:
            raise NotFoundError("Plan not found", details={"code": plan_code})
        customer = await self._ensure_customer(user_id=user_id, email=email)
        session = await self._gateway.create_checkout_session(
            customer_id=customer.stripe_customer_id,
            price_id=plan.stripe_price_id or plan.code,
            plan_code=plan.code,
            user_id=user_id,
            trial_days=plan.trial_days,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        self._audit.record(action="commerce.checkout_started", actor_user_id=user_id,
                           meta={"plan": plan.code, "session": session.id})
        return session.url

    async def portal_url(self, *, user_id: uuid.UUID, return_url: str) -> str:
        customer = await self._customers.get_for_user(user_id)
        if customer is None:
            raise ValidationFailedError(
                "No billing profile yet — start a subscription first"
            )
        return await self._gateway.create_portal_session(
            customer_id=customer.stripe_customer_id, return_url=return_url
        )

    async def _ensure_customer(self, *, user_id: uuid.UUID,
                               email: str) -> BillingCustomer:
        existing = await self._customers.get_for_user(user_id)
        if existing is not None:
            return existing
        stripe_id = await self._gateway.create_customer(email=email, user_id=user_id)
        customer = BillingCustomer(user_id=user_id, stripe_customer_id=stripe_id)
        self._customers.add(customer)
        await self._customers.flush()
        return customer

    # ── Entitlement & reads ────────────────────────────────────
    async def entitlement(self, user_id: uuid.UUID) -> dict[str, Any]:
        subscription = await self._subscriptions.latest_for_user(user_id)
        if subscription is not None and subscription.status in PREMIUM_STATUSES:
            return {"premium": True, "source": "subscription",
                    "subscription": subscription}
        org_ids = await self._users.organization_ids_for(user_id)
        license_ = await self._licenses.active_for_organizations(org_ids)
        if license_ is not None:
            return {"premium": True, "source": "license",
                    "subscription": subscription}
        return {"premium": False, "source": "none", "subscription": subscription}

    async def my_payments(self, user_id: uuid.UUID) -> list[Payment]:
        return await self._payments.list_for_user(user_id)

    # ── Refunds (admin-initiated, webhook-confirmed) ───────────
    async def request_refund(self, *, payment_id: uuid.UUID,
                             amount_cents: int | None, actor: uuid.UUID) -> str:
        payment = await self._payments.get(payment_id)
        if payment.status != "succeeded":
            raise ValidationFailedError("Only succeeded payments can be refunded",
                                        details={"status": payment.status})
        refund_id = await self._gateway.refund_payment(
            payment_intent_id=payment.stripe_payment_intent_id,
            amount_cents=amount_cents,
        )
        self._audit.record(action="commerce.refund_requested", actor_user_id=actor,
                           entity_type="payment", entity_id=payment.id,
                           meta={"refund": refund_id,
                                 "amount_cents": amount_cents})
        return refund_id

    # ── Enterprise licensing ───────────────────────────────────
    async def create_license(self, data: dict[str, Any],
                             actor: uuid.UUID) -> EnterpriseLicense:
        license_ = EnterpriseLicense(**data)
        self._licenses.add(license_)
        await self._licenses.flush()
        self._audit.record(action="commerce.license_created", actor_user_id=actor,
                           entity_type="enterprise_license", entity_id=license_.id)
        return license_

    async def list_licenses(self, *, limit: int, offset: int) -> list[EnterpriseLicense]:
        return await self._licenses.list(limit=limit, offset=offset)

    # ── Webhooks ───────────────────────────────────────────────
    async def handle_webhook(self, payload: bytes, signature: str) -> None:
        event = self._gateway.verify_webhook(payload, signature)
        event_id = str(event.get("id", ""))
        event_type = str(event.get("type", ""))
        if not event_id:
            raise ValidationFailedError("Webhook event missing id")
        if await self._webhooks.seen(event_id):
            return  # at-least-once delivery: replay is a no-op
        data = (event.get("data") or {}).get("object") or {}

        handler = {
            "checkout.session.completed": self._on_checkout_completed,
            "customer.subscription.created": self._on_subscription_upsert,
            "customer.subscription.updated": self._on_subscription_upsert,
            "customer.subscription.deleted": self._on_subscription_deleted,
            "invoice.paid": self._on_invoice_paid,
            "invoice.payment_failed": self._on_invoice_failed,
            "charge.refunded": self._on_charge_refunded,
        }.get(event_type)
        if handler is not None:
            await handler(data)
        else:
            log.info("webhook_ignored", type=event_type)

        self._webhooks.add(WebhookEvent(stripe_event_id=event_id, type=event_type,
                                        payload=event))
        await self._webhooks.flush()

    async def _resolve_user_id(self, data: dict[str, Any]) -> uuid.UUID | None:
        customer_id = str(data.get("customer", "") or "")
        if customer_id:
            customer = await self._customers.get_by_stripe_id(customer_id)
            if customer is not None:
                return customer.user_id
        reference = data.get("client_reference_id")
        if reference:
            try:
                return uuid.UUID(str(reference))
            except ValueError:
                return None
        return None

    async def _on_checkout_completed(self, data: dict[str, Any]) -> None:
        user_id = await self._resolve_user_id(data)
        stripe_sub_id = str(data.get("subscription", "") or "")
        if user_id is None or not stripe_sub_id:
            log.warning("checkout_completed_unresolvable")
            return
        if await self._subscriptions.get_by_stripe_id(stripe_sub_id) is None:
            self._subscriptions.add(Subscription(
                user_id=user_id, stripe_subscription_id=stripe_sub_id,
                status=SUB_INCOMPLETE,
            ))
            await self._subscriptions.flush()

    async def _on_subscription_upsert(self, data: dict[str, Any]) -> None:
        stripe_sub_id = str(data.get("id", "") or "")
        if not stripe_sub_id:
            return
        subscription = await self._subscriptions.get_by_stripe_id(stripe_sub_id)
        if subscription is None:
            user_id = await self._resolve_user_id(data)
            if user_id is None:
                log.warning("subscription_event_unresolvable", sub=stripe_sub_id)
                return
            subscription = Subscription(user_id=user_id,
                                        stripe_subscription_id=stripe_sub_id)
            self._subscriptions.add(subscription)
        plan_code = str(((data.get("metadata") or {}).get("plan_code")) or "")
        if plan_code and subscription.plan_id is None:
            plan = await self._plans.get_by_code(plan_code)
            if plan is not None:
                subscription.plan_id = plan.id
        subscription.status = str(data.get("status", subscription.status))
        subscription.current_period_end = _from_unix(data.get("current_period_end"))
        subscription.trial_end = _from_unix(data.get("trial_end"))
        subscription.cancel_at_period_end = bool(data.get("cancel_at_period_end", False))
        await self._subscriptions.flush()
        await self.emit(DomainEvent(name=ev.SUBSCRIPTION_CHANGED,
                                    user_id=subscription.user_id,
                                    payload={"status": subscription.status}))

    async def _on_subscription_deleted(self, data: dict[str, Any]) -> None:
        subscription = await self._subscriptions.get_by_stripe_id(
            str(data.get("id", "") or "")
        )
        if subscription is None:
            return
        subscription.status = SUB_CANCELED
        await self._subscriptions.flush()
        await self.emit(DomainEvent(name=ev.SUBSCRIPTION_CHANGED,
                                    user_id=subscription.user_id,
                                    payload={"status": SUB_CANCELED}))

    async def _on_invoice_paid(self, data: dict[str, Any]) -> None:
        user_id = await self._resolve_user_id(data)
        if user_id is None:
            log.warning("invoice_paid_unresolvable")
            return
        intent = str(data.get("payment_intent") or f"inv:{data.get('id', '')}")
        if await self._payments.get_by_intent(intent) is not None:
            return
        self._payments.add(Payment(
            user_id=user_id,
            stripe_payment_intent_id=intent,
            stripe_invoice_id=str(data.get("id", "") or ""),
            amount_cents=int(data.get("amount_paid", 0) or 0),
            currency=str(data.get("currency", "usd") or "usd"),
            status="succeeded",
            description="Subscription payment",
        ))
        await self._payments.flush()
        await self.emit(DomainEvent(name=ev.PURCHASE_COMPLETED, user_id=user_id,
                                    payload={"amount_cents":
                                             int(data.get("amount_paid", 0) or 0)}))

    async def _on_invoice_failed(self, data: dict[str, Any]) -> None:
        stripe_sub_id = str(data.get("subscription", "") or "")
        subscription = (await self._subscriptions.get_by_stripe_id(stripe_sub_id)
                        if stripe_sub_id else None)
        if subscription is not None:
            subscription.status = SUB_PAST_DUE
            await self._subscriptions.flush()
            await self.emit(DomainEvent(name=ev.SUBSCRIPTION_CHANGED,
                                        user_id=subscription.user_id,
                                        payload={"status": SUB_PAST_DUE}))

    async def _on_charge_refunded(self, data: dict[str, Any]) -> None:
        intent = str(data.get("payment_intent", "") or "")
        payment = await self._payments.get_by_intent(intent) if intent else None
        if payment is None:
            return
        payment.status = "refunded"
        payment.refunded_amount_cents = int(data.get("amount_refunded", 0) or 0)
        await self._payments.flush()
        await self.emit(DomainEvent(name=ev.PAYMENT_REFUNDED, user_id=payment.user_id,
                                    payload={"amount_cents":
                                             payment.refunded_amount_cents}))


def build_commerce_service(session, event_bus: EventBus) -> CommerceService:
    """Composition helper (module boundary rule)."""
    from app.modules.commerce.gateway import get_gateway
    from app.modules.users.service import build_user_service

    return CommerceService(
        plans=PlanRepository(session),
        customers=BillingCustomerRepository(session),
        subscriptions=SubscriptionRepository(session),
        payments=PaymentRepository(session),
        webhooks=WebhookEventRepository(session),
        licenses=EnterpriseLicenseRepository(session),
        gateway=get_gateway(),
        users=build_user_service(session, event_bus),
        audit=AuditService(session),
        event_bus=event_bus,
    )
