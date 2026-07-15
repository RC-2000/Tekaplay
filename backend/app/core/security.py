"""Password hashing and token primitives.

Argon2id for passwords. JWTs are short-lived access tokens only; refresh
tokens are opaque random strings stored HASHED (sha256) server-side, so a
database leak never leaks usable credentials. All auth flows build on the
four primitives here — nothing else in the codebase touches jwt or argon2.
"""
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings
from app.core.errors import AuthenticationError

_hasher = PasswordHasher()  # argon2id, library defaults reviewed against OWASP


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, candidate: str) -> bool:
    try:
        return _hasher.verify(password_hash, candidate)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    """Returns (token, expires_in_seconds)."""
    settings = get_settings()
    expires_in = settings.access_token_expire_minutes * 60
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(claims, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str) -> uuid.UUID:
    settings = get_settings()
    try:
        claims = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid or expired access token") from exc
    if claims.get("type") != "access":
        raise AuthenticationError("Invalid token type")
    try:
        return uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Invalid token subject") from exc


def generate_opaque_token() -> str:
    """For refresh tokens and action tokens (email verification, password reset)."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Deterministic hash for server-side storage/lookup of opaque tokens."""
    return hashlib.sha256(token.encode()).hexdigest()
