import uuid

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Bus, CurrentUser, DbSession, require_permission
from app.events.bus import EventBus
from app.modules.content.repository import (
    CampaignRepository,
    CertificationRepository,
    ContentProjectRepository,
    ContentVersionRepository,
    CourseRepository,
    MissionRepository,
)
from app.modules.content.schemas import (
    CampaignCreate,
    CertificationCreate,
    CertificationNode,
    CourseCreate,
    DraftIn,
    MissionCreate,
    NodeOut,
    ProjectCreate,
    ProjectOut,
    ReviewIn,
    ValidateIn,
    ValidateOut,
    VersionDetail,
    VersionOut,
)
from app.modules.content.service import ContentService
from app.modules.runtime.service import build_runtime_service
from app.modules.users.audit import AuditService

router = APIRouter(prefix="/content", tags=["content"])

AUTHOR = require_permission("content.author")
PUBLISH = require_permission("content.publish")


def _service(session: AsyncSession, bus: EventBus) -> ContentService:
    return ContentService(
        projects=ContentProjectRepository(session),
        versions=ContentVersionRepository(session),
        certifications=CertificationRepository(session),
        campaigns=CampaignRepository(session),
        courses=CourseRepository(session),
        missions=MissionRepository(session),
        runtime=build_runtime_service(session, bus),
        audit=AuditService(session),
        event_bus=bus,
    )


# ── Library (players) ──────────────────────────────────────────
@router.get("/library", response_model=list[CertificationNode])
async def library(_: CurrentUser, session: DbSession, bus: Bus) -> list[CertificationNode]:
    return await _service(session, bus).library()


# ── Catalog administration ─────────────────────────────────────
@router.post("/certifications", response_model=NodeOut, status_code=201,
             dependencies=[PUBLISH])
async def create_certification(body: CertificationCreate, session: DbSession,
                               bus: Bus) -> NodeOut:
    record = await _service(session, bus).create_certification(body.model_dump())
    return NodeOut.model_validate(record)


@router.post("/campaigns", response_model=NodeOut, status_code=201,
             dependencies=[PUBLISH])
async def create_campaign(body: CampaignCreate, session: DbSession, bus: Bus) -> NodeOut:
    record = await _service(session, bus).create_campaign(body.model_dump())
    return NodeOut.model_validate(record)


@router.post("/courses", response_model=NodeOut, status_code=201,
             dependencies=[PUBLISH])
async def create_course(body: CourseCreate, session: DbSession, bus: Bus) -> NodeOut:
    record = await _service(session, bus).create_course(body.model_dump())
    return NodeOut.model_validate(record)


@router.post("/missions", response_model=NodeOut, status_code=201,
             dependencies=[PUBLISH])
async def create_mission(body: MissionCreate, session: DbSession, bus: Bus) -> NodeOut:
    record = await _service(session, bus).create_mission(body.model_dump())
    return NodeOut.model_validate(record)


# ── Creator Studio: projects & versions ────────────────────────
@router.post("/projects", response_model=ProjectOut, status_code=201,
             dependencies=[AUTHOR])
async def create_project(body: ProjectCreate, current_user: CurrentUser,
                         session: DbSession, bus: Bus) -> ProjectOut:
    project = await _service(session, bus).create_project(
        slug=body.slug, title=body.title, certification=body.certification,
        owner_id=current_user.id,
    )
    return ProjectOut.model_validate(project)


@router.get("/projects", response_model=list[ProjectOut], dependencies=[AUTHOR])
async def list_projects(
    session: DbSession, bus: Bus,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ProjectOut]:
    projects = await _service(session, bus).list_projects(limit=limit, offset=offset)
    return [ProjectOut.model_validate(p) for p in projects]


@router.get("/projects/{project_id}", response_model=ProjectOut,
            dependencies=[AUTHOR])
async def get_project(project_id: uuid.UUID, session: DbSession, bus: Bus) -> ProjectOut:
    return ProjectOut.model_validate(await _service(session, bus).get_project(project_id))


@router.post("/projects/{project_id}/versions", response_model=VersionOut,
             status_code=201, dependencies=[AUTHOR])
async def create_draft(project_id: uuid.UUID, body: DraftIn,
                       current_user: CurrentUser, session: DbSession,
                       bus: Bus) -> VersionOut:
    version = await _service(session, bus).create_draft(
        project_id=project_id, definition=body.definition, notes=body.notes,
        actor=current_user.id,
    )
    return VersionOut.model_validate(version)


@router.get("/projects/{project_id}/versions", response_model=list[VersionOut],
            dependencies=[AUTHOR])
async def list_versions(project_id: uuid.UUID, session: DbSession,
                        bus: Bus) -> list[VersionOut]:
    versions = await _service(session, bus).list_versions(project_id)
    return [VersionOut.model_validate(v) for v in versions]


@router.get("/versions/{version_id}", response_model=VersionDetail,
            dependencies=[AUTHOR])
async def get_version(version_id: uuid.UUID, session: DbSession,
                      bus: Bus) -> VersionDetail:
    return VersionDetail.model_validate(
        await _service(session, bus).get_version(version_id)
    )


@router.put("/versions/{version_id}", response_model=VersionOut,
            dependencies=[AUTHOR])
async def update_draft(version_id: uuid.UUID, body: DraftIn,
                       current_user: CurrentUser, session: DbSession,
                       bus: Bus) -> VersionOut:
    version = await _service(session, bus).update_draft(
        version_id=version_id, definition=body.definition, notes=body.notes,
        actor=current_user.id,
    )
    return VersionOut.model_validate(version)


@router.post("/validate", response_model=ValidateOut, dependencies=[AUTHOR])
async def validate(body: ValidateIn, session: DbSession, bus: Bus) -> ValidateOut:
    return _service(session, bus).validate_definition(body.definition)


@router.post("/versions/{version_id}/submit", response_model=VersionOut,
             dependencies=[AUTHOR])
async def submit(version_id: uuid.UUID, current_user: CurrentUser,
                 session: DbSession, bus: Bus) -> VersionOut:
    version = await _service(session, bus).submit(version_id=version_id,
                                                  actor=current_user.id)
    return VersionOut.model_validate(version)


@router.post("/versions/{version_id}/approve", response_model=VersionOut,
             dependencies=[PUBLISH])
async def approve(version_id: uuid.UUID, body: ReviewIn, current_user: CurrentUser,
                  session: DbSession, bus: Bus) -> VersionOut:
    version = await _service(session, bus).approve(version_id=version_id,
                                                   note=body.note,
                                                   actor=current_user.id)
    return VersionOut.model_validate(version)


@router.post("/versions/{version_id}/reject", response_model=VersionOut,
             dependencies=[PUBLISH])
async def reject(version_id: uuid.UUID, body: ReviewIn, current_user: CurrentUser,
                 session: DbSession, bus: Bus) -> VersionOut:
    version = await _service(session, bus).reject(version_id=version_id,
                                                  note=body.note,
                                                  actor=current_user.id)
    return VersionOut.model_validate(version)


@router.post("/versions/{version_id}/publish", response_model=VersionOut,
             dependencies=[PUBLISH])
async def publish(version_id: uuid.UUID, current_user: CurrentUser,
                  session: DbSession, bus: Bus) -> VersionOut:
    version = await _service(session, bus).publish(version_id=version_id,
                                                   actor=current_user.id)
    return VersionOut.model_validate(version)


@router.post("/versions/{version_id}/rollback", response_model=VersionOut,
             dependencies=[PUBLISH])
async def rollback(version_id: uuid.UUID, current_user: CurrentUser,
                   session: DbSession, bus: Bus) -> VersionOut:
    version = await _service(session, bus).publish(version_id=version_id,
                                                   actor=current_user.id,
                                                   is_rollback=True)
    return VersionOut.model_validate(version)
