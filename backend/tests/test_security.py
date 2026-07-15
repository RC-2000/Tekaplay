import uuid

import pytest

from app.core import security
from app.core.errors import AuthenticationError


def test_password_hash_roundtrip():
    h = security.hash_password("hunter2hunter2")
    assert h != "hunter2hunter2"
    assert security.verify_password(h, "hunter2hunter2")
    assert not security.verify_password(h, "wrong")


def test_access_token_roundtrip():
    user_id = uuid.uuid4()
    token, expires_in = security.create_access_token(user_id)
    assert expires_in > 0
    assert security.decode_access_token(token) == user_id


def test_tampered_token_rejected():
    token, _ = security.create_access_token(uuid.uuid4())
    with pytest.raises(AuthenticationError):
        security.decode_access_token(token[:-2] + "xx")


def test_opaque_tokens_unique_and_hashed():
    a, b = security.generate_opaque_token(), security.generate_opaque_token()
    assert a != b
    assert len(security.hash_token(a)) == 64
