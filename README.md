# QuestForge

An immersive educational gaming platform. Professional certifications and exams taught through
interactive, story-driven games — where **games are data, not code**, executed by a generic
Game Runtime Engine.

> The name `questforge` is a working codename. Rename via a single find/replace; nothing is
> coupled to it.

## Repository layout

```
questforge/
├── docs/                  Architecture and design documents (start with ARCHITECTURE.md)
├── backend/               FastAPI application (modular monolith, service-per-module)
│   ├── app/
│   │   ├── core/          Config, logging, errors, security primitives
│   │   ├── db/            SQLAlchemy engine, session, base model mixins
│   │   ├── api/v1/        Versioned HTTP API (thin — delegates to services)
│   │   ├── modules/       One package per bounded context (auth, users, content, runtime, ...)
│   │   ├── repositories/  Data-access layer (repository pattern)
│   │   ├── services/      Business logic layer
│   │   ├── events/        In-process event bus (swap for SQS/Kafka later)
│   │   └── workers/       Celery app and task registration
│   ├── alembic/           Database migrations
│   └── tests/
├── frontend/              Next.js (App Router) + TypeScript + Tailwind
├── infra/                 Infrastructure notes and future IaC
└── .github/workflows/     CI pipeline
```

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000 (docs at /api/v1/docs)
- Web: http://localhost:3000

Then run migrations and bootstrap the first admin:

```bash
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.create_admin admin@example.com <password>
docker compose exec api python -m app.scripts.seed_demo   # publish the example mission
```

Content authoring flows through `/api/v1/content`: projects hold immutable
version snapshots moving draft → in_review → approved → published, with
rollback republishing any superseded version. The library tree for players
is at `GET /api/v1/content/library`.

## Local development without Docker

Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Make targets

`make up`, `make down`, `make test`, `make lint`, `make migrate`, `make revision m="message"`

## Reading order

1. `docs/ARCHITECTURE.md` — system design, module boundaries, migration path to AWS
2. `backend/app/core/config.py` — every environment variable the system understands
3. `backend/app/events/bus.py` — the event backbone everything else plugs into
