import jwt
import pytest
from app.core.security import create_access_token, decode_access_token

def test_jwt_package_is_pyjwt():
    assert hasattr(jwt, "encode"), "jwt must have 'encode' function"
    assert hasattr(jwt, "decode"), "jwt must have 'decode' function"
    assert hasattr(jwt, "PyJWTError"), "jwt must define PyJWTError"

def test_token_encode_and_decode_roundtrip():
    token = create_access_token({"sub": "test-uuid-1234", "role": "user"})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "test-uuid-1234"
    assert payload["role"] == "user"
