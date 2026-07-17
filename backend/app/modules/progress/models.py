import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MissionProgress(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Aggregated per (user, mission-slug) — slugs are the stable identity of
    a mission across republished definition rows. Mastery = correct/answered."""

    __tablename__ = "mission_progress"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_progress_user_slug"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    completions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    best_ending: Mapped[str | None] = mapped_column(String(120))
    questions_answered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    questions_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlayerStreak(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Daily streak, UTC-based for now (user-timezone streaks are a later
    refinement noted in the roadmap)."""

    __tablename__ = "player_streaks"
    __table_args__ = (UniqueConstraint("user_id", name="uq_streak_user"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_activity_date: Mapped[date | None] = mapped_column(Date)
