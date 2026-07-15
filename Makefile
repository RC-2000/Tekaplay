.PHONY: up down logs test lint fmt migrate revision

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api worker

test:
	cd backend && pytest -q

lint:
	cd backend && ruff check app tests && mypy app
	cd frontend && npm run lint

fmt:
	cd backend && ruff format app tests

migrate:
	cd backend && alembic upgrade head

revision:
	cd backend && alembic revision --autogenerate -m "$(m)"
