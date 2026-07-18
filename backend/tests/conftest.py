"""Test bootstrap.

Defaults to file-backed SQLite (fast, zero infra) via env vars set BEFORE the
app is imported; CI overrides DATABASE_URL to real PostgreSQL. Tables come
from metadata here; migration correctness is checked separately in CI by
running `alembic upgrade head` against Postgres.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("AI_PROVIDER", "echo")
os.environ.setdefault("AI_DISPATCH", "inline")

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.base import Base
from app.db.session import engine
from app.main import app  # noqa: E402  (env must be set first)


@pytest.fixture(autouse=True)
async def _fresh_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def registered_user(client):
    body = {"email": "alice@example.com", "password": "correct-horse-battery",
            "display_name": "Alice"}
    resp = await client.post("/api/v1/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    return body


@pytest.fixture
async def auth_tokens(client, registered_user):
    resp = await client.post("/api/v1/auth/login", json={
        "email": registered_user["email"], "password": registered_user["password"]})
    assert resp.status_code == 200, resp.text
    return resp.json()
