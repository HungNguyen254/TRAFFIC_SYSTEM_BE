from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


def test_password_hashing():
    raw_password = "supersecretpassword123"
    hashed = hash_password(raw_password)

    assert hashed != raw_password
    assert "$" in hashed
    assert verify_password(raw_password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_jwt_token_cycle():
    data = {"sub": "42", "role": "ADMIN", "username": "adminuser"}
    token = create_access_token(data)

    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "ADMIN"
    assert payload["username"] == "adminuser"
    assert "exp" in payload


def test_decode_invalid_token():
    invalid_token = "invalid.token.string"
    payload = decode_access_token(invalid_token)
    assert payload is None
