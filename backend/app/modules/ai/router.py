import uuid

from fastapi import APIRouter

from app.api.deps import Bus, CurrentUser, DbSession
from app.core.config import get_settings
from app.core.ratelimit import check_rate_limit
from app.modules.ai import features
from app.modules.ai.models import AIRequest, AIResponse
from app.modules.ai.schemas import AIRequestIn, AIRequestOut, AIResponseOut, FeatureOut
from app.modules.ai.service import build_ai_service

router = APIRouter(prefix="/ai", tags=["ai"])


def _out(request: AIRequest, response: AIResponse | None) -> AIRequestOut:
    return AIRequestOut(
        id=request.id,
        feature=request.feature,
        status=request.status,
        personalized=request.personalized,
        error=request.error,
        created_at=request.created_at,
        completed_at=request.completed_at,
        response=AIResponseOut.model_validate(response) if response else None,
    )


@router.get("/features", response_model=list[FeatureOut])
async def list_features(_: CurrentUser) -> list[FeatureOut]:
    return [FeatureOut(**f) for f in features.catalog()]


@router.post("/requests", response_model=AIRequestOut, status_code=202)
async def submit(body: AIRequestIn, current_user: CurrentUser,
                 session: DbSession, bus: Bus) -> AIRequestOut:
    settings = get_settings()
    await check_rate_limit(f"ai:{current_user.id}",
                           limit=settings.ai_rate_limit_per_minute,
                           window_seconds=60)
    service = build_ai_service(session, bus)
    request = await service.submit(user_id=current_user.id,
                                   feature_name=body.feature,
                                   raw_input=body.input)
    _, response = await service.get_owned(user_id=current_user.id,
                                          request_id=request.id)
    return _out(request, response)


@router.get("/requests/{request_id}", response_model=AIRequestOut)
async def get_request(request_id: uuid.UUID, current_user: CurrentUser,
                      session: DbSession, bus: Bus) -> AIRequestOut:
    service = build_ai_service(session, bus)
    request, response = await service.get_owned(user_id=current_user.id,
                                                request_id=request_id)
    return _out(request, response)
