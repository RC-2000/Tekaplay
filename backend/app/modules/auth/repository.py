import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.modules.auth.models import ActionToken, OAuthAccount, RefreshToken
from app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    model = RefreshToken

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def revoke_family(self, family_id: uuid.UUID) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )


class ActionTokenRepository(BaseRepository[ActionToken]):
    model = ActionToken

    async def get_valid(self, token_hash: str, purpose: str) -> ActionToken | None:
        stmt = select(ActionToken).where(
            ActionToken.token_hash == token_hash,
            ActionToken.purpose == purpose,
            ActionToken.used_at.is_(None),
            ActionToken.expires_at > datetime.now(UTC),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class OAuthAccountRepository(BaseRepository[OAuthAccount]):
    model = OAuthAccount

    async def get_by_provider_account(
        self, provider: str, provider_account_id: str
    ) -> OAuthAccount | None:
        stmt = select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_account_id == provider_account_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
