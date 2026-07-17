import uuid

from sqlalchemy import select

from app.modules.users.models import Permission, RolePermission, Role, User, UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_many(self, ids: list[uuid.UUID]) -> list[User]:
        if not ids:
            return []
        stmt = self._base_query().where(User.id.in_(ids))
        return list((await self.session.execute(stmt)).scalars())

    async def get_by_email(self, email: str) -> User | None:
        stmt = self._base_query().where(User.email == email.strip().lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_permission_codes(self, user_id: uuid.UUID) -> set[str]:
        stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user_id)
        )
        return set((await self.session.execute(stmt)).scalars())

    async def get_role_by_name(self, name: str) -> Role | None:
        stmt = select(Role).where(Role.name == name)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def assign_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
        exists = await self.session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id,
                UserRole.organization_id.is_(None),
            )
        )
        if exists.scalar_one_or_none() is None:
            self.session.add(UserRole(user_id=user_id, role_id=role_id))
