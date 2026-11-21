import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class AdminUserUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    role: Literal["user", "admin"]

    @field_validator("full_name")
    @classmethod
    def full_name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Tên người dùng không được để trống.")
        return value


class AdminUserResponse(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    role: str
    created_at: datetime


class AdminUserListResponse(BaseModel):
    users: list[AdminUserResponse]
