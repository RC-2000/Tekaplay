"""AI request/response persistence: full audit and cost trail for every
completion, and the durable layer of the response cache (prompt_hash)."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import PortableJSON

STATUS_QUEUED = "queued"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


class AIRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_requests"
    __table_args__ = (Index("ix_ai_requests_hash_status", "prompt_hash", "status"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False,
                                        default=STATUS_QUEUED)
    input: Mapped[dict[str, Any]] = mapped_column(PortableJSON, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    personalized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIResponse(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_responses"

    request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai_requests.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_input: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
