"""Bootstrap the first admin: python -m app.scripts.create_admin email password [name]

Idempotent: promotes an existing user instead of failing. Registration is
audited under action 'admin.bootstrapped'.
"""
import asyncio
import sys

from app.core.security import hash_password
from app.db.session import SessionFactory
from app.modules.users.audit import AuditService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository


async def main(email: str, password: str, display_name: str = "Admin") -> None:
    email = email.strip().lower()
    async with SessionFactory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_email(email)
        if user is None:
            user = User(email=email, password_hash=hash_password(password),
                        display_name=display_name)
            repo.add(user)
            await repo.flush()
        role = await repo.get_role_by_name("admin")
        if role is None:
            raise SystemExit("Run migrations first: role 'admin' not found")
        await repo.assign_role(user.id, role.id)
        AuditService(session).record(action="admin.bootstrapped", actor_user_id=user.id,
                                     entity_type="user", entity_id=user.id)
        await session.commit()
        print(f"admin ready: {email}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("usage: python -m app.scripts.create_admin <email> <password> [name]")
    asyncio.run(main(*sys.argv[1:4]))
