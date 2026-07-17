import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PlayerInventoryItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Cross-session collectible mirror of in-game inventory events, scoped by
    the mission slug the item came from (item keys are content-local)."""

    __tablename__ = "player_inventory"
    __table_args__ = (
        UniqueConstraint("user_id", "source_slug", "item_key",
                         name="uq_inventory_item"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_slug: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    item_key: Mapped[str] = mapped_column(String(200), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
