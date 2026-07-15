import uuid

from app.db.session import SessionFactory
from app.modules.users.models import Permission, Role, RolePermission, User, UserRole


async def _grant_permission(email: str, code: str) -> None:
    """Wire user → role → permission directly at the DB layer for the test."""
    from sqlalchemy import select

    async with SessionFactory() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        perm = Permission(code=code, description="test")
        role = Role(name=f"test-role-{uuid.uuid4().hex[:8]}")
        session.add_all([perm, role])
        await session.flush()
        session.add_all([
            RolePermission(role_id=role.id, permission_id=perm.id),
            UserRole(user_id=user.id, role_id=role.id),
        ])
        await session.commit()


async def test_permission_denied_without_role(client, auth_tokens):
    resp = await client.get("/api/v1/users",
                            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "permission_denied"
    assert resp.json()["error"]["details"]["required"] == "users.read"


async def test_permission_granted_with_role(client, auth_tokens, registered_user):
    await _grant_permission(registered_user["email"], "users.read")
    resp = await client.get("/api/v1/users",
                            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["email"] == registered_user["email"]


async def test_anonymous_rejected(client):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "authentication_required"
