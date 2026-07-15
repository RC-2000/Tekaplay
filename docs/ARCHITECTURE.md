# QuestForge — System Architecture

**Status:** Living document. Slice 1 (foundation) is implemented; later sections describe committed design that subsequent slices fill in.

## 1. What this system is

QuestForge is an educational gaming platform that teaches professional certifications (AWS, Azure, CISSP, PMP, CPA, SAT, university courses, and any future domain) through interactive, story-driven games. The defining architectural commitment is that **games are data, not code**. A single, generic Game Runtime Engine interprets JSON game definitions; no certification-specific logic ever exists in the platform. Adding a new certification, exam, or entire subject area is a content operation performed in the Creator Studio, not a deployment.

The content hierarchy every game follows is: Certification → Campaign → Course → Mission → Scene → Challenge → Events → Rewards. The runtime walks this tree, evaluates conditions against player state, emits events, and grants rewards. Everything else on the platform — progress, achievements, XP, analytics, adaptive learning, notifications — is a consumer of the events that walk produces.

## 2. Architectural style: modular monolith, microservice-ready

The platform is built as a **modular monolith**: one deployable FastAPI application whose internals are partitioned into strictly bounded modules, one per logical service (Authentication, User, Content, Game Runtime, Progress, Inventory, Achievement, XP, Analytics, Notification, AI, Search, Commerce, Admin, Creator Studio, Realtime). This is a deliberate choice, not a shortcut. A true microservice fleet at day one would multiply operational cost and slow iteration while the domain model is still settling; a classic monolith would rot into coupling. The modular monolith gives module isolation now and cheap extraction later.

The extraction guarantee comes from three enforced rules, encoded in `backend/app/modules/README.md` and the base classes:

1. A module may only be entered through its **service interface** or the **event bus**. No module imports another module's models or repositories.
2. All infrastructure (database, cache, storage, queue, LLM) is consumed through neutral interfaces owned by `core`/`db`/`events`, injected via constructor.
3. All cross-module *reactions* (achievement unlocks, analytics, notifications) are event subscriptions, never direct calls. Direct service calls are reserved for cases where the caller needs the result synchronously.

When a module needs independent scaling (AI and Realtime are the likely first candidates), its service interface becomes an HTTP/gRPC client, its tables move via logical replication, and its event subscriptions move to the external broker. Callers do not change.

The frontend never touches the database. All access flows through the versioned HTTP API. The backend is stateless: no session affinity, no local disk state, all shared state in PostgreSQL, Redis, or object storage. Any number of API instances and Celery workers can run in parallel from day one.

## 3. Layering inside the backend

Requests flow through four layers with strict downward dependencies:

**Router → Service → Repository → Database**, with the **Event Bus** as a lateral spine any service can publish to.

The **router** layer (`app/api/v1/`) is transport only: it decodes HTTP, invokes a service, encodes the response. It contains no business rules, which is what allows the same services to later back websockets (Realtime), workers, and native clients without duplication.

The **service** layer owns business logic and transactions. Services receive repositories, the event bus, and other services' interfaces through their constructors (dependency injection via FastAPI's dependency system, overridable wholesale in tests). Services raise typed `AppError` subclasses; they never construct HTTP responses.

The **repository** layer (`app/repositories/base.py` plus one repository per module) is the only code that touches SQLAlchemy. It enforces platform-wide invariants centrally: soft-deleted rows are invisible by default, lookups by ID raise `NotFoundError` uniformly, optimistic-concurrency conflicts surface as `ConflictError` (HTTP 409, retryable).

The **error envelope** is uniform across the entire API. Every failure, expected or not, serializes as `{"error": {"code", "message", "details", "retryable", "request_id"}}`. `code` is a stable machine identifier clients can branch on; `retryable` tells clients (and the retry queues) whether repeating the request can succeed; `request_id` links any user report to the exact structured log lines. Handlers live in `app/main.py`; nothing else formats errors.

## 4. Event-driven core

`app/events/bus.py` defines the platform's most important contract: `DomainEvent`, an envelope carrying a stable dot-namespaced name, timestamp, optional user and correlation IDs, and a payload. The event catalog grows additively — names and payload fields are never renamed or removed once published, only added — so subscribers written today keep working forever.

The initial catalog (implemented as modules land):

`mission.started`, `mission.finished`, `scene.entered`, `scene.completed`, `challenge.presented`, `question.answered` (payload distinguishes correct/incorrect), `hint.used`, `inventory.changed`, `xp.awarded`, `level.up`, `achievement.unlocked`, `save.created`, `session.resumed`, `player.quit`, `purchase.completed`, `subscription.changed`, `ai.request.completed`, `content.published`, `user.registered`.

Analytics subscribes to `*` and persists everything. Achievements, adaptive learning, streaks, and notifications subscribe selectively. The Game Runtime emits and never knows who listens — this is precisely what keeps it generic.

The bus ships as an in-process async pub/sub with isolated handler failures (a broken subscriber can never break the emitting business action). The `EventBus` protocol is intentionally two methods, so the Redis Streams implementation (near-term, for durability across processes) and the SQS/EventBridge implementation (AWS migration) are drop-in. Handlers must be idempotent from day one, because at-least-once delivery is the assumption the external brokers will impose.

## 5. Game Runtime Engine (design contract for slice 3)

The runtime is an interpreter over a versioned JSON schema. The committed shape:

A **game definition** is a validated JSON document (`schema_version` at the root) stored as the single sanctioned "large JSON blob" in the database, in `published_versions`, immutable once published. Everything else in the database stays normalized. The definition declares scenes as nodes in a directed graph; edges carry **conditions** evaluated against **player state** (variables, flags, inventory, mastery scores). Scenes contain ordered **elements**: dialogue (with branching and NPC memory references), media (audio/video/image via asset IDs, never URLs), and **challenges**.

Challenges are the extensibility point. Each challenge has a `type` (`quiz`, `drag_drop`, `ordering`, `flashcards`, `hotspot`, `code_challenge`, `simulation`, `decision_tree`, ...) resolved through a **challenge-type registry**. Adding a game type means registering a validator + evaluator on the backend and a renderer component on the frontend; the runtime core never changes. This registry is the "future plugin support" seam.

Player state is a versioned document per (user, game): variables, flags, inventory, current position, save points. It is written with **optimistic concurrency** (the `VersionedMixin`) because autosave, checkpoint saves, and challenge submissions can race. Every mutation the runtime makes emits domain events. Resume is trivially correct because state is the single source of truth: the client is a renderer of server state, which is also what makes future React Native/Electron/Tauri clients cheap.

## 6. Data layer

PostgreSQL 16, accessed via SQLAlchemy 2 async with Alembic migrations. Universal rules are encoded once in `app/db/base.py` mixins: UUID primary keys, timezone-aware `created_at`/`updated_at`, soft delete (`deleted_at`) where auditability matters, and `version` columns for optimistic concurrency on hot rows. Data is normalized; the only sanctioned JSON blobs are game definitions (immutable rows; republishing a slug creates a new row and moves a `live` flag, so in-flight sessions are never mutated underneath), content-version snapshots, player-state documents, and event payloads.

Tables arrive with their modules, in dependency order: identity first (users, organizations, roles, permissions, audit_logs), then content (games, campaigns, courses, modules, missions, scenes, dialogue, questions, npcs, assets, asset_metadata, localization, draft_versions, published_versions), then player systems (progress, inventory, xp, achievements, badges, leaderboards, notifications), then commerce (payments, subscriptions), then platform (analytics_events, ai_requests, ai_responses, feature_flags, support_tickets, system_settings). Foreign keys, constraints, and indexes are declared in the models so autogenerate keeps migrations honest; every index must be justified by a query.

Redis serves four distinct roles under distinct key prefixes: cache (AI responses, rendered content), rate limiting, Celery broker/results, and realtime pub/sub. Nothing durable lives only in Redis.

## 7. Asynchronous work

Celery workers handle everything that shouldn't block a request: AI calls, email, analytics fan-out beyond the in-process bus, media processing, exports. Three queues from the start — `default`, `ai` (slow, provider-rate-limited), `events` — so a flood in one cannot starve the others. Tasks are idempotent and accept an **idempotency key**; retryable operations check the key before doing work. `task_acks_late` is on, so a dying worker's tasks are redelivered rather than lost. This maps one-to-one onto SQS semantics for the AWS migration.

## 8. AI service boundary

The frontend never calls an LLM. All AI features (hints, explanations, NPC dialogue, question/mission/scenario generation, flashcards, adaptive difficulty, study plans, weakness detection, exam readiness) go through the AI module, which queues requests on the `ai` Celery queue, records `ai_requests`/`ai_responses` rows for audit and cost tracking, and caches deterministic responses in Redis keyed by a content hash. Provider access sits behind a single gateway interface so models and vendors are swappable per feature via configuration.

## 9. Security

Passwords are hashed with Argon2id. Auth issues short-lived JWT access tokens (15 min) and rotating refresh tokens (revocable, stored hashed); Google and Microsoft OAuth feed the same identity model. Authorization is role- **and** permission-based: roles are bundles of granular permissions, checked in a single dependency at the router layer and re-checked in services for defense in depth. Every privileged action writes an `audit_logs` row.

Platform-wide: HTTPS only, strict CORS from configuration, CSRF protection on cookie-carrying routes, rate limiting in Redis, SQLAlchemy bound parameters everywhere (no string SQL), output encoding against XSS, secrets exclusively via environment/secret manager (the structlog processor chain redacts sensitive keys as a backstop — see `core/logging.py`), dependency and container scanning in CI, automated backups with tested restores. OWASP ASVS is the review checklist.

## 10. Observability

Structured JSON logs via structlog, automatically enriched with `request_id`, `correlation_id`, and `user_id` bound by middleware — the game/mission IDs join the context as the runtime lands. `/health/live` and `/health/ready` implement standard liveness/readiness semantics. OpenTelemetry tracing and Prometheus metrics attach at the middleware and repository layers (slice: observability), exported to Grafana; Sentry captures exceptions with the request context attached. The correlation ID flows from HTTP header → logs → events → Celery tasks, so one user action is traceable end to end.

## 11. Portability: local → managed → AWS

The platform runs identically in three postures because every provider is consumed through a neutral interface:

Local development uses Docker Compose (Postgres, Redis, API, worker, web). The initial production posture uses Neon (Postgres), Upstash (Redis), Cloudflare R2 (S3-compatible object storage), and Cloudflare CDN. The AWS posture swaps to RDS, ElastiCache, S3, ECS Fargate behind an ALB, SQS as the Celery broker, and CloudWatch — **as configuration and IaC changes only**. The guarantees making that true: database access is a SQLAlchemy URL; Redis is a URL; object storage is only ever spoken to through the S3 API; queueing is a Celery broker URL; the event bus is a two-method protocol. No application code imports a provider SDK outside the designated gateway modules.

## 12. Frontend architecture

Next.js (App Router) + TypeScript, strict mode. Server state lives in React Query (all fetching through the single typed client in `src/lib/api-client.ts`, which decodes the standard error envelope in exactly one place); client/game-session state lives in Zustand stores; the PixiJS canvas hosts game scene rendering with React owning all chrome around it; Framer Motion handles UI animation. The design system is token-driven: semantic CSS variables (`surface`, `ink`, `accent`, ...) consumed through Tailwind, so dark/light theming and future white-labeling are palette swaps, not component rewrites. Components ship with loading, empty, and error states as first-class variants. Accessibility (keyboard navigation, focus visibility, reduced motion, contrast) is a review gate, not a retrofit.

## 13. Testing and CI/CD

The pyramid: unit tests for services and the runtime interpreter (the bulk, run against fakes injected through DI); integration tests against real Postgres in CI; API contract tests through the ASGI transport; frontend component and E2E tests; plus dedicated game-definition simulation tests that walk published JSON through the runtime and assert on the emitted event stream — this last category is what makes "games are data" safe, because content changes get regression-tested like code.

GitHub Actions runs lint → type check → test → build → image build on every PR (implemented). The pipeline extends to security scanning, staging deploy, smoke tests, manual approval, and production deploy as hosting is provisioned. API versioning (`/api/v1`) plus additive-only event and schema evolution is the compatibility policy that lets deploys be frequent and boring.

## 14. Build order

1. **Foundation** — this slice: repo, layering, error model, event bus, DI, CI, app shells. ✅
2. **Identity & data core** — full schema for users/orgs/roles/permissions/audit, Alembic baseline (`0001_identity_core`), auth module (Argon2, JWT + rotating refresh tokens with family-based reuse detection, Google/Microsoft OAuth gateway, email verification + password reset via events), RBAC `require_permission` dependency. ✅
3. **Game Runtime** — JSON definition schema v1 with publish-time graph validation (`runtime/definition.py`), pure interpreter (`runtime/engine.py`: view computation, advance/choose/answer, conditions, effects, endings), challenge-type registry with quiz/ordering/text_input built-ins, player-state document under automatic optimistic locking (`VersionedMixin` → 409 on races), save points + restore + resume-anywhere, full event emission, sample mission (`examples/aws_cp_mission_1.json`) with simulation tests asserting on the emitted event stream. ✅
4. **Content & Creator Studio (backend)** — normalized catalog (certifications → campaigns → courses → missions) with a player-facing library tree; authoring projects with append-only immutable versions; draft → in_review → approved → published lifecycle with rejection notes; publish integrates with the runtime via its service interface (new immutable live row per publish); rollback = republishing a superseded version through the same path; validation endpoint for the Studio. Visual builder UI lands with the frontend slice. ✅
5. **Player systems** — progress, XP, achievements, inventory, leaderboards, streaks (all as event subscribers).
6. **AI service**, **Commerce (Stripe)**, **Search**, **Notifications**, **Admin panel**, **Observability hardening**, **AWS IaC** — in whichever order business priority dictates; the boundaries above make them independent.
