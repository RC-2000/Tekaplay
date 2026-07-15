"""User-facing DTOs. Models never cross the API boundary."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    avatar_url: str | None
    locale: str
    timezone: str
    theme: str
    email_verified_at: datetime | None
    created_at: datetime


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=1024)
    locale: str | None = Field(default=None, max_length=16)
    timezone: str | None = Field(default=None, max_length=64)
    theme: str | None = Field(default=None, pattern="^(light|dark|system)$")


class UserPage(BaseModel):
    items: list[UserOut]
    limit: int
    offset: int
