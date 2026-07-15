"""Shared column types. JSONB on PostgreSQL, JSON on SQLite (tests)."""
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

PortableJSON = JSON().with_variant(JSONB(), "postgresql")
