import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PlayerXp(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "player_xp"
    __table_args__ = (UniqueConstraint("user_id", name="uq_player_xp_user"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    total_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class XpTransaction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Append-only ledger: the aggregate is always recomputable."""

    __tablename__ = "xp_transactions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
