"""Runtime persistence.

game_definitions holds published definitions as IMMUTABLE rows — the single
sanctioned large-JSON exception in the schema (docs/ARCHITECTURE.md §6).
Republishing a slug creates a new row and moves the `live` flag; in-flight
sessions keep playing the row they started on, so content updates can never
corrupt a running game.
game_sessions carries the per-(user, game) player-state document guarded by
optimistic concurrency: autosave, checkpoints, and answer submissions can
race, and the version column turns silent lost-updates into explicit 409s.
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    VersionedMixin,
)
from app.db.types import PortableJSON


class GameDefinitionRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "game_definitions"
    __table_args__ = (
        # exactly one live definition per slug (partial unique on both dialects)
        Index("uq_game_definitions_slug_live", "slug", unique=True,
              postgresql_where=text("live"), sqlite_where=text("live")),
    )

    slug: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    live: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    certification: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="published")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(PortableJSON, nullable=False)
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class GameSession(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin):
    __tablename__ = "game_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("game_definitions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    state: Mapped[dict[str, Any]] = mapped_column(PortableJSON, nullable=False)
    ending_id: Mapped[str | None] = mapped_column(String(120))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))



class SavePoint(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Named snapshot of a session's state document (checkpoint saves)."""

    __tablename__ = "save_points"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(PortableJSON, nullable=False)
