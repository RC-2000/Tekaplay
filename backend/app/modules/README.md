# Modules — bounded contexts

Each subpackage here is one service from the architecture (auth, users,
content, runtime, progress, inventory, achievements, xp, analytics,
notifications, ai, search, commerce, admin, studio, realtime).

Required internal shape (enforced by review, mirrored by every module):

```
modules/<name>/
├── models.py      SQLAlchemy models (register in alembic/env.py)
├── schemas.py     Pydantic request/response DTOs
├── repository.py  Extends BaseRepository
├── service.py     Business logic; depends on repository + EventBus
├── router.py      FastAPI routes; thin; mounted in api/v1/router.py
├── events.py      Event names this module publishes + subscribers it registers
└── tasks.py       Celery tasks (optional)
```

Rules:
- A module may import `core`, `db`, `events`, `repositories.base`, `services.base`.
- A module may import another module ONLY via its service interface, never its
  models or repository. This is the microservice-extraction seam.
- All cross-module reactions go through the event bus when eventual consistency
  is acceptable; direct service calls only when the caller needs the result.

## Documented boundary exceptions

- **auth ↔ users** form a single *identity* context: credentials, sessions,
  and OAuth links are attributes of the user aggregate, so `auth` may import
  `users`' repository and models. If identity is ever extracted, these two
  modules move together. No other module may import either one's models —
  everything else goes through their service interfaces or events
  (`user.registered`, `user.deleted`, `auth.login_succeeded`, ...).
