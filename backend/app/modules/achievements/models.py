import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Achievement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Admin-defined catalog. Game definitions reference achievements by code
    (unlock_achievement effect); undefined codes are ignored at grant time so
    content can ship ahead of catalog entries without breaking players."""

    __tablename__ = "achievements"

    code: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    icon: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    xp_reward: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class UserAchievement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    achievement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("achievements.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
