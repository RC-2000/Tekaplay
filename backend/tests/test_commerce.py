"""Commerce with the fake gateway: plans, checkout, the webhook-driven
subscription lifecycle, payment/refund flow, idempotency, signature
enforcement, and enterprise-license entitlement."""
import json
import uuid as uuidlib

import pytest

from tests.test_rbac import _grant_permission


@pytest.fixture
def auth_headers(auth_tokens):
    return {"Authorization": f"Bearer {auth_tokens['access_token']}"}


@pytest.fixture
async def admin_headers(client, auth_headers, registered_user):
    await _grant_permission(registered_user["email"], "commerce.manage")
    return auth_headers  # same account, now with manage rights


async def _webhook(client, event: dict, signature: str = "fake-signature"):
    return await client.post(
        "/api/v1/commerce/webhooks/stripe",
        content=json.dumps(event).encode(),
        headers={"stripe-signature": signature,
                 "content-type": "application/json"},
    )


def _event(event_type: str, obj: dict, event_id: str | None = None) -> dict:
    return {"id": event_id or f"evt_{uuidlib.uuid4().hex[:16]}",
            "type": event_type, "data": {"object": obj}}


@pytest.fixture
async def plan(client, admin_headers):
    resp = await client.post("/api/v1/commerce/plans", headers=admin_headers,
                             json={"code": "pro-monthly", "name": "Pro",
                                   "price_cents": 1500, "trial_days": 7})
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
async def customer_id(client, auth_headers, plan) -> str:
    """Run checkout so the billing customer mapping exists, then return the
    fake Stripe customer id webhooks will reference."""
    resp = await client.post("/api/v1/commerce/checkout", headers=auth_headers,
                             json={"plan_code": "pro-monthly",
                                   "success_url": "https://app.example/ok",
                                   "cancel_url": "https://app.example/cancel"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["checkout_url"].startswith("https://billing.example/checkout/")

    from sqlalchemy import select

    from app.db.session import SessionFactory
    from app.modules.commerce.models import BillingCustomer

    async with SessionFactory() as session:
        row = (await session.execute(select(BillingCustomer))).scalar_one()
        return row.stripe_customer_id


async def test_plans_visible_and_manage_gated(client, auth_headers, plan):
    plans = (await client.get("/api/v1/commerce/plans", headers=auth_headers)).json()
    assert [p["code"] for p in plans] == ["pro-monthly"]

    # the plan fixture granted manage to this account; a fresh account
    # must still be denied
    other = {"email": "pleb@example.com", "password": "correct-horse-battery",
             "display_name": "Pleb"}
    await client.post("/api/v1/auth/register", json=other)
    login = await client.post("/api/v1/auth/login", json={
        "email": other["email"], "password": other["password"]})
    fresh = {"Authorization": f"Bearer {login.json()['access_token']}"}
    denied = await client.post("/api/v1/commerce/plans", headers=fresh,
                               json={"code": "x", "name": "X", "price_cents": 1})
    assert denied.status_code == 403


async def test_subscription_lifecycle_via_webhooks(client, auth_headers,
                                                   customer_id):
    # before any webhook: no premium
    before = (await client.get("/api/v1/commerce/subscription",
                               headers=auth_headers)).json()
    assert before == {"premium": False, "source": "none", "subscription": None}

    sub_id = "sub_fake_001"
    assert (await _webhook(client, _event("checkout.session.completed", {
        "customer": customer_id, "subscription": sub_id,
    }))).status_code == 204
    assert (await _webhook(client, _event("customer.subscription.updated", {
        "id": sub_id, "customer": customer_id, "status": "trialing",
        "current_period_end": 4102444800, "trial_end": 4102444800,
        "cancel_at_period_end": False,
        "metadata": {"plan_code": "pro-monthly"},
    }))).status_code == 204

    trialing = (await client.get("/api/v1/commerce/subscription",
                                 headers=auth_headers)).json()
    assert trialing["premium"] is True
    assert trialing["source"] == "subscription"
    assert trialing["subscription"]["status"] == "trialing"
    assert trialing["subscription"]["plan_id"] is not None

    # trial converts, invoice paid → payment recorded
    await _webhook(client, _event("customer.subscription.updated", {
        "id": sub_id, "customer": customer_id, "status": "active",
        "current_period_end": 4102444800,
    }))
    await _webhook(client, _event("invoice.paid", {
        "id": "in_001", "customer": customer_id, "payment_intent": "pi_001",
        "amount_paid": 1500, "currency": "usd", "subscription": sub_id,
    }))
    payments = (await client.get("/api/v1/commerce/payments/me",
                                 headers=auth_headers)).json()
    assert len(payments) == 1
    assert payments[0]["amount_cents"] == 1500
    assert payments[0]["status"] == "succeeded"

    # payment failure → past_due → premium lost (grace policy is explicit)
    await _webhook(client, _event("invoice.payment_failed", {
        "id": "in_002", "customer": customer_id, "subscription": sub_id,
    }))
    past_due = (await client.get("/api/v1/commerce/subscription",
                                 headers=auth_headers)).json()
    assert past_due["subscription"]["status"] == "past_due"
    assert past_due["premium"] is False

    # cancellation
    await _webhook(client, _event("customer.subscription.deleted", {"id": sub_id}))
    canceled = (await client.get("/api/v1/commerce/subscription",
                                 headers=auth_headers)).json()
    assert canceled["subscription"]["status"] == "canceled"


async def test_webhook_idempotency(client, auth_headers, customer_id):
    event = _event("invoice.paid", {
        "id": "in_dup", "customer": customer_id, "payment_intent": "pi_dup",
        "amount_paid": 900, "currency": "usd",
    }, event_id="evt_replayed")
    assert (await _webhook(client, event)).status_code == 204
    assert (await _webhook(client, event)).status_code == 204  # Stripe retry
    payments = (await client.get("/api/v1/commerce/payments/me",
                                 headers=auth_headers)).json()
    assert len(payments) == 1


async def test_webhook_signature_enforced(client):
    resp = await _webhook(client, _event("invoice.paid", {}), signature="wrong")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "authentication_required"


async def test_purchase_event_emitted(client, auth_headers, customer_id):
    from app.events.bus import DomainEvent, bus

    captured: list[DomainEvent] = []

    async def collector(event: DomainEvent) -> None:
        captured.append(event)

    bus.subscribe("purchase.completed", collector)
    await _webhook(client, _event("invoice.paid", {
        "id": "in_evt", "customer": customer_id, "payment_intent": "pi_evt",
        "amount_paid": 1500, "currency": "usd",
    }))
    assert any(e.payload.get("amount_cents") == 1500 for e in captured)
    assert all(e.user_id is not None for e in captured)


async def test_refund_flow(client, auth_headers, admin_headers, customer_id):
    await _webhook(client, _event("invoice.paid", {
        "id": "in_r", "customer": customer_id, "payment_intent": "pi_refund",
        "amount_paid": 1500, "currency": "usd",
    }))
    payments = (await client.get("/api/v1/commerce/payments/me",
                                 headers=auth_headers)).json()
    payment_id = payments[0]["id"]

    requested = await client.post(
        f"/api/v1/commerce/payments/{payment_id}/refund",
        headers=admin_headers, json={})
    assert requested.status_code == 202
    assert requested.json()["refund_id"].startswith("re_fake_")

    # Stripe confirms via webhook
    await _webhook(client, _event("charge.refunded", {
        "payment_intent": "pi_refund", "amount_refunded": 1500,
    }))
    refunded = (await client.get("/api/v1/commerce/payments/me",
                                 headers=auth_headers)).json()[0]
    assert refunded["status"] == "refunded"
    assert refunded["refunded_amount_cents"] == 1500

    # double refund request rejected
    again = await client.post(
        f"/api/v1/commerce/payments/{payment_id}/refund",
        headers=admin_headers, json={})
    assert again.status_code == 422


async def test_enterprise_license_grants_premium(client, auth_headers,
                                                 admin_headers, registered_user):
    from sqlalchemy import select

    from app.db.session import SessionFactory
    from app.modules.users.models import Organization, OrganizationMember, User

    async with SessionFactory() as session:
        user_id = (await session.execute(select(User.id).where(
            User.email == registered_user["email"]))).scalar_one()
        org = Organization(name="Meridian Orbital", slug="meridian")
        session.add(org)
        await session.flush()
        session.add(OrganizationMember(organization_id=org.id, user_id=user_id))
        await session.commit()
        org_id = str(org.id)

    created = await client.post("/api/v1/commerce/licenses", headers=admin_headers,
                                json={"organization_id": org_id, "seats": 25,
                                      "notes": "Annual enterprise deal"})
    assert created.status_code == 201

    entitlement = (await client.get("/api/v1/commerce/subscription",
                                    headers=auth_headers)).json()
    assert entitlement["premium"] is True
    assert entitlement["source"] == "license"

    licenses = (await client.get("/api/v1/commerce/licenses",
                                 headers=admin_headers)).json()
    assert licenses[0]["seats"] == 25


async def test_portal_requires_billing_profile(client, auth_headers):
    resp = await client.post("/api/v1/commerce/portal", headers=auth_headers,
                             json={"return_url": "https://app.example/settings"})
    assert resp.status_code == 422
