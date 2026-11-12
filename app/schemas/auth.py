import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


def validate_password_strength(password: str) -> str:
    if not any(character.isupper() for character in password):
        raise ValueError("Mật khẩu phải có ít nhất 1 ký tự viết hoa.")
    if not any(character.isdecimal() for character in password):
        raise ValueError("Mật khẩu phải có ít nhất 1 chữ số.")
    if not any(not character.isalnum() for character in password):
        raise ValueError("Mật khẩu phải có ít nhất 1 ký tự đặc biệt.")
    return password


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, password: str) -> str:
        return validate_password_strength(password)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)

    @field_validator("new_password")
    @classmethod
    def new_password_must_be_strong(cls, password: str) -> str:
        return validate_password_strength(password)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: uuid.UUID


class UserResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    created_at: datetime
