"""AI orchestration: validate → hash → persist → dispatch → complete.

Caching is two-layer: Redis (fast, best-effort) in front of the database
(durable, deterministic — any completed response with the same prompt_hash).
Personalized features fold the user id into the hash so context never leaks
across users. Every completion or failure is persisted and emitted, giving
the audit/cost trail the admin panel will read.
"""
import hashlib
import json
import uuid
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.events.bus import DomainEvent, EventBus
from app.modules.ai import cache, features
from app.modules.ai import events as ev
from app.modules.ai.models import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_QUEUED,
    AIRequest,
    AIResponse,
)
from app.modules.ai.provider import AIProvider
from app.modules.ai.repository import AIRequestRepository, AIResponseRepository
from app.modules.progress.service import ProgressService
from app.services.base import BaseService

log = get_logger(__name__)


def compute_prompt_hash(feature: str, normalized_input: dict,
                        user_id: uuid.UUID | None) -> str:
    payload = feature + json.dumps(normalized_input, sort_keys=True, default=str)
    if user_id is not None:  # personalized: cache scope is per-user
        payload += str(user_id)
    return hashlib.sha256(payload.encode()).hexdigest()


class AIService(BaseService):
    def __init__(
        self,
        requests: AIRequestRepository,
        responses: AIResponseRepository,
        provider: AIProvider,
        event_bus: EventBus,
        progress: ProgressService | None = None,
    ) -> None:
        super().__init__(event_bus)
        self._requests = requests
        self._responses = responses
        self._provider = provider
        self._progress = progress

    # ── Intake ─────────────────────────────────────────────────
    async def submit(self, *, user_id: uuid.UUID, feature_name: str,
                     raw_input: dict) -> AIRequest:
        feature = features.get(feature_name)
        data = features.validate_input(feature_name, raw_input)
        normalized = data.model_dump()
        prompt_hash = compute_prompt_hash(
            feature_name, normalized, user_id if feature.personalized else None
        )
        request = AIRequest(
            user_id=user_id,
            feature=feature_name,
            status=STATUS_QUEUED,
            input=normalized,
            prompt_hash=prompt_hash,
            personalized=feature.personalized,
        )
        self._requests.add(request)
        await self._requests.flush()

        if get_settings().ai_dispatch == "inline":
            await self.process(request.id)
        else:
            # Enqueued pre-commit; the task retries briefly if the row isn't
            # visible yet (see tasks.py).
            from app.modules.ai.tasks import process_ai_request

            process_ai_request.delay(str(request.id))
        return request

    async def get_owned(self, *, user_id: uuid.UUID,
                        request_id: uuid.UUID) -> tuple[AIRequest, AIResponse | None]:
        request = await self._requests.get(request_id)
        if request.user_id != user_id:  # 404, not 403: don't leak existence
            raise NotFoundError("AI request not found",
                                details={"id": str(request_id)})
        response = await self._responses.get_for_request(request.id)
        return request, response

    # ── Processing (inline or worker) ──────────────────────────
    async def process(self, request_id: uuid.UUID) -> AIRequest:
        request = await self._requests.get(request_id)
        if request.status != STATUS_QUEUED:  # idempotent redelivery guard
            return request

        # Durable cache first (DB), Redis in front of it.
        cached_content = await cache.get_cached(request.prompt_hash)
        if cached_content is None:
            previous = await self._responses.latest_completed_for_hash(
                request.prompt_hash
            )
            if previous is not None:
                cached_content = previous.content
        if cached_content is not None:
            settings = get_settings()
            self._responses.add(AIResponse(
                request_id=request.id, provider="cache", model=settings.ai_model,
                content=cached_content, cached=True,
            ))
            return await self._complete(request)

        try:
            prompt = await self._build_prompt(request)
            completion = await self._provider.complete(prompt)
        except Exception as exc:  # noqa: BLE001 — failures are data, not crashes
            log.error("ai_request_failed", request_id=str(request.id),
                      feature=request.feature, error=str(exc))
            request.status = STATUS_FAILED
            request.error = str(exc)[:2000]
            request.completed_at = datetime.now(UTC)
            await self._requests.flush()
            await self.emit(DomainEvent(name=ev.REQUEST_FAILED,
                                        user_id=request.user_id,
                                        payload={"request_id": str(request.id),
                                                 "feature": request.feature}))
            return request

        self._responses.add(AIResponse(
            request_id=request.id,
            provider=completion.provider,
            model=completion.model,
            content=completion.content,
            tokens_input=completion.tokens_input,
            tokens_output=completion.tokens_output,
            latency_ms=completion.latency_ms,
            cached=False,
        ))
        await cache.set_cached(request.prompt_hash, completion.content)
        return await self._complete(request)

    async def _complete(self, request: AIRequest) -> AIRequest:
        request.status = STATUS_COMPLETED
        request.completed_at = datetime.now(UTC)
        await self._requests.flush()
        await self.emit(DomainEvent(name=ev.REQUEST_COMPLETED,
                                    user_id=request.user_id,
                                    payload={"request_id": str(request.id),
                                             "feature": request.feature}))
        return request

    async def _build_prompt(self, request: AIRequest) -> str:
        feature = features.get(request.feature)
        data = feature.input_model.model_validate(request.input)
        context: dict = {}
        if feature.personalized and self._progress is not None:
            context["progress_summary"] = await self._progress_summary(request.user_id)
        return feature.build_prompt(data, context)

    async def _progress_summary(self, user_id: uuid.UUID) -> str:
        records = await self._progress.list_for_user(user_id)
        if not records:
            return "No history yet."
        def mastery(r):
            return (r.questions_correct / r.questions_answered
                    if r.questions_answered else 0.0)
        lines = [
            f"- {r.slug}: {r.questions_correct}/{r.questions_answered} correct "
            f"({mastery(r):.0%}), status {r.status}"
            for r in sorted(records, key=mastery)[:10]
        ]
        return "\n".join(lines)


def build_ai_service(session, event_bus: EventBus) -> AIService:
    """Composition helper (module boundary rule)."""
    from app.modules.ai.provider import get_provider
    from app.modules.progress.service import build_progress_service

    return AIService(
        requests=AIRequestRepository(session),
        responses=AIResponseRepository(session),
        provider=get_provider(),
        event_bus=event_bus,
        progress=build_progress_service(session, event_bus),
    )
