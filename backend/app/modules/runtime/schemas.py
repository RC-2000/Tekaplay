import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DefinitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    certification: str
    schema_version: int
    created_at: datetime


class DefinitionDetail(DefinitionOut):
    description: str = ""


class PublishDefinitionRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    definition: dict[str, Any]


class StartSessionRequest(BaseModel):
    definition_id: uuid.UUID
    replay: bool = False


class HUD(BaseModel):
    variables: dict[str, Any]
    flags: list[str]
    inventory: dict[str, int]
    xp_earned: int
    achievements: list[str]


class SessionView(BaseModel):
    session_id: uuid.UUID
    definition_id: uuid.UUID
    status: str
    scene_id: str | None
    scene_title: str | None
    passives: list[dict[str, Any]]
    interactive: dict[str, Any] | None
    can_advance: bool
    ending: dict[str, Any] | None
    hud: HUD


class ChooseRequest(BaseModel):
    element_id: str
    option_id: str


class AnswerRequest(BaseModel):
    element_id: str
    response: dict[str, Any]


class AnswerOut(BaseModel):
    correct: bool
    score: float
    feedback: str
    view: SessionView


class SaveRequest(BaseModel):
    label: str = Field(min_length=1, max_length=120)


class SaveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    created_at: datetime
