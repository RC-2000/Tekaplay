"""Authoring lifecycle and catalog assembly.

State machine (append-only history, no rewrites):

    draft ──submit──▶ in_review ──approve──▶ approved ──publish──▶ published
      ▲                   │                                            │
      └── new draft ◀── reject (terminal, kept for the record)         │
                                                     previous live ──▶ superseded

Rollback = publish() on a superseded version: it becomes the live definition
again through the exact same code path, and the version it replaces becomes
superseded. Only `draft` versions are mutable.

Publishing crosses into the runtime module strictly through its service
interface (build_runtime_service) — the microservice-extraction seam.
"""
import uuid
from datetime import UTC, datetime

from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.events.bus import DomainEvent, EventBus
from app.modules.content import events as ev
from app.modules.content.models import (
    Campaign,
    Certification,
    ContentProject,
    ContentVersion,
    Course,
    Mission,
)
from app.modules.content.repository import (
    CampaignRepository,
    CertificationRepository,
    ContentProjectRepository,
    ContentVersionRepository,
    CourseRepository,
    MissionRepository,
)
from app.modules.content.schemas import (
    CampaignNode,
    CertificationNode,
    CourseNode,
    MissionNode,
    ValidateOut,
)
from app.modules.runtime.definition import parse_definition
from app.modules.runtime.service import RuntimeService
from app.modules.users.audit import AuditService
from app.services.base import BaseService

DRAFT = "draft"
IN_REVIEW = "in_review"
APPROVED = "approved"
REJECTED = "rejected"
PUBLISHED = "published"
SUPERSEDED = "superseded"


class ContentService(BaseService):
    def __init__(
        self,
        projects: ContentProjectRepository,
        versions: ContentVersionRepository,
        certifications: CertificationRepository,
        campaigns: CampaignRepository,
        courses: CourseRepository,
        missions: MissionRepository,
        runtime: RuntimeService,
        audit: AuditService,
        event_bus: EventBus,
    ) -> None:
        super().__init__(event_bus)
        self._projects = projects
        self._versions = versions
        self._certifications = certifications
        self._campaigns = campaigns
        self._courses = courses
        self._missions = missions
        self._runtime = runtime
        self._audit = audit

    # ── Validation (Studio's "validate" button) ────────────────
    def validate_definition(self, raw: dict) -> ValidateOut:
        try:
            parse_definition(raw)
            return ValidateOut(valid=True)
        except ValidationFailedError as exc:
            errors = exc.details.get("errors")
            return ValidateOut(valid=False,
                               errors=errors if isinstance(errors, list)
                               else [{"msg": exc.message, **exc.details}])

    # ── Projects ───────────────────────────────────────────────
    async def create_project(self, *, slug: str, title: str, certification: str,
                             owner_id: uuid.UUID) -> ContentProject:
        if await self._projects.get_by_slug(slug) is not None:
            raise ConflictError("A project with this slug already exists",
                                details={"slug": slug})
        project = ContentProject(slug=slug, title=title,
                                 certification=certification, owner_id=owner_id)
        self._projects.add(project)
        await self._projects.flush()
        return project

    async def get_project(self, project_id: uuid.UUID) -> ContentProject:
        return await self._projects.get(project_id)

    async def list_projects(self, *, limit: int, offset: int) -> list[ContentProject]:
        return await self._projects.list(limit=limit, offset=offset)

    # ── Versions ───────────────────────────────────────────────
    async def create_draft(self, *, project_id: uuid.UUID, definition: dict,
                           notes: str, actor: uuid.UUID) -> ContentVersion:
        project = await self._projects.get(project_id)
        version = ContentVersion(
            project_id=project.id,
            version_number=await self._versions.next_version_number(project.id),
            status=DRAFT,
            definition=definition,
            notes=notes,
            created_by=actor,
        )
        self._versions.add(version)
        await self._versions.flush()
        await self.emit(DomainEvent(name=ev.DRAFT_CREATED, user_id=actor,
                                    payload=self._payload(version)))
        return version

    async def update_draft(self, *, version_id: uuid.UUID, definition: dict,
                           notes: str, actor: uuid.UUID) -> ContentVersion:
        version = await self._versions.get(version_id)
        self._require_status(version, {DRAFT}, "Only drafts can be edited")
        version.definition = definition
        version.notes = notes
        await self._versions.flush()
        return version

    async def list_versions(self, project_id: uuid.UUID) -> list[ContentVersion]:
        await self._projects.get(project_id)  # 404 if the project is gone
        return await self._versions.list_for_project(project_id)

    async def get_version(self, version_id: uuid.UUID) -> ContentVersion:
        return await self._versions.get(version_id)

    # ── Lifecycle transitions ──────────────────────────────────
    async def submit(self, *, version_id: uuid.UUID, actor: uuid.UUID) -> ContentVersion:
        version = await self._versions.get(version_id)
        self._require_status(version, {DRAFT}, "Only drafts can be submitted")
        parse_definition(version.definition)  # gate: broken content never reaches review
        version.status = IN_REVIEW
        version.submitted_at = datetime.now(UTC)
        await self._versions.flush()
        await self.emit(DomainEvent(name=ev.SUBMITTED, user_id=actor,
                                    payload=self._payload(version)))
        return version

    async def approve(self, *, version_id: uuid.UUID, note: str,
                      actor: uuid.UUID) -> ContentVersion:
        version = await self._review(version_id, APPROVED, note, actor)
        await self.emit(DomainEvent(name=ev.APPROVED, user_id=actor,
                                    payload=self._payload(version)))
        return version

    async def reject(self, *, version_id: uuid.UUID, note: str,
                     actor: uuid.UUID) -> ContentVersion:
        version = await self._review(version_id, REJECTED, note, actor)
        await self.emit(DomainEvent(name=ev.REJECTED, user_id=actor,
                                    payload=self._payload(version)))
        return version

    async def publish(self, *, version_id: uuid.UUID, actor: uuid.UUID,
                      is_rollback: bool = False) -> ContentVersion:
        version = await self._versions.get(version_id)
        allowed = {SUPERSEDED} if is_rollback else {APPROVED, SUPERSEDED}
        self._require_status(
            version, allowed,
            "Only a superseded version can be rolled back to" if is_rollback
            else "Only approved (or superseded, for rollback) versions can be published",
        )
        project = await self._projects.get(version.project_id)

        # The runtime creates a new immutable live row; old sessions unaffected.
        await self._runtime.upsert_live_definition(
            slug=project.slug, raw=version.definition, published_by=actor
        )

        if project.live_version_id and project.live_version_id != version.id:
            try:
                previous = await self._versions.get(project.live_version_id)
                previous.status = SUPERSEDED
            except NotFoundError:  # pragma: no cover — defensive
                pass
        version.status = PUBLISHED
        version.published_at = datetime.now(UTC)
        project.live_version_id = version.id
        await self._versions.flush()

        self._audit.record(
            action="content.rolled_back" if is_rollback else "content.published",
            actor_user_id=actor, entity_type="content_version", entity_id=version.id,
            meta={"project": project.slug, "version": version.version_number},
        )
        if is_rollback:
            await self.emit(DomainEvent(name=ev.ROLLED_BACK, user_id=actor,
                                        payload=self._payload(version)))
        return version

    # ── Catalog ────────────────────────────────────────────────
    async def create_certification(self, data: dict) -> Certification:
        record = Certification(**data)
        self._certifications.add(record)
        await self._certifications.flush()
        return record

    async def create_campaign(self, data: dict) -> Campaign:
        await self._certifications.get(data["certification_id"])
        record = Campaign(**data)
        self._campaigns.add(record)
        await self._campaigns.flush()
        return record

    async def create_course(self, data: dict) -> Course:
        await self._campaigns.get(data["campaign_id"])
        record = Course(**data)
        self._courses.add(record)
        await self._courses.flush()
        return record

    async def create_mission(self, data: dict) -> Mission:
        await self._courses.get(data["course_id"])
        if data.get("project_id") is not None:
            await self._projects.get(data["project_id"])
        record = Mission(**data)
        self._missions.add(record)
        await self._missions.flush()
        return record

    async def library(self) -> list[CertificationNode]:
        """The player-facing tree: four ordered queries, assembled in memory,
        with each mission resolved to its live runtime definition (if any)."""
        certifications = await self._certifications.ordered()
        campaigns = await self._campaigns.ordered()
        courses = await self._courses.ordered()
        missions = await self._missions.ordered()

        live_by_slug = await self._runtime.live_definitions_by_slug()
        project_slugs: dict[uuid.UUID, str] = {
            p.id: p.slug for p in await self._projects.list(limit=1000, offset=0)
        }

        mission_nodes: dict[uuid.UUID, list[MissionNode]] = {}
        for m in missions:
            definition_id = None
            if m.project_id is not None:
                slug = project_slugs.get(m.project_id)
                record = live_by_slug.get(slug) if slug else None
                definition_id = record.id if record else None
            node = MissionNode.model_validate(m)
            node.definition_id = definition_id
            mission_nodes.setdefault(m.course_id, []).append(node)

        course_nodes: dict[uuid.UUID, list[CourseNode]] = {}
        for c in courses:
            node = CourseNode.model_validate(c)
            node.missions = mission_nodes.get(c.id, [])
            course_nodes.setdefault(c.campaign_id, []).append(node)

        campaign_nodes: dict[uuid.UUID, list[CampaignNode]] = {}
        for cp in campaigns:
            node = CampaignNode.model_validate(cp)
            node.courses = course_nodes.get(cp.id, [])
            campaign_nodes.setdefault(cp.certification_id, []).append(node)

        tree: list[CertificationNode] = []
        for cert in certifications:
            node = CertificationNode.model_validate(cert)
            node.campaigns = campaign_nodes.get(cert.id, [])
            tree.append(node)
        return tree

    # ── Internals ──────────────────────────────────────────────
    async def _review(self, version_id: uuid.UUID, new_status: str, note: str,
                      actor: uuid.UUID) -> ContentVersion:
        version = await self._versions.get(version_id)
        self._require_status(version, {IN_REVIEW},
                             "Only versions in review can be approved or rejected")
        version.status = new_status
        version.review_note = note
        version.reviewed_at = datetime.now(UTC)
        await self._versions.flush()
        self._audit.record(action=f"content.{new_status}", actor_user_id=actor,
                           entity_type="content_version", entity_id=version.id)
        return version

    @staticmethod
    def _require_status(version: ContentVersion, allowed: set[str], message: str) -> None:
        if version.status not in allowed:
            raise ValidationFailedError(
                message, details={"status": version.status,
                                  "allowed": sorted(allowed)}
            )

    @staticmethod
    def _payload(version: ContentVersion) -> dict:
        return {"project_id": str(version.project_id),
                "version_id": str(version.id),
                "version_number": version.version_number}
