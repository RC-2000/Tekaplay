from sqlalchemy import select

from app.modules.ai.models import STATUS_COMPLETED, AIRequest, AIResponse
from app.repositories.base import BaseRepository


class AIRequestRepository(BaseRepository[AIRequest]):
    model = AIRequest


class AIResponseRepository(BaseRepository[AIResponse]):
    model = AIResponse

    async def get_for_request(self, request_id) -> AIResponse | None:
        stmt = select(AIResponse).where(AIResponse.request_id == request_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def latest_completed_for_hash(self, prompt_hash: str) -> AIResponse | None:
        """Durable cache lookup: any completed response for the same prompt.
        Personalization is already baked into the hash."""
        stmt = (
            select(AIResponse)
            .join(AIRequest, AIRequest.id == AIResponse.request_id)
            .where(AIRequest.prompt_hash == prompt_hash,
                   AIRequest.status == STATUS_COMPLETED)
            .order_by(AIResponse.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
