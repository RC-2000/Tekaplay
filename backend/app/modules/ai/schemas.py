import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AIRequestIn(BaseModel):
    feature: str = Field(min_length=1, max_length=60)
    input: dict[str, Any] = Field(default_factory=dict)


class AIResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    content: str
    provider: str
    model: str
    cached: bool
    tokens_input: int
    tokens_output: int
    latency_ms: int


class AIRequestOut(BaseModel):
    id: uuid.UUID
    feature: str
    status: str
    personalized: bool
    error: str
    created_at: datetime
    completed_at: datetime | None
    response: AIResponseOut | None = None


class FeatureOut(BaseModel):
    name: str
    description: str
    personalized: bool
