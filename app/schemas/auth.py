import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ValidationInfo, field_validator


def validate_password_strength(password: str) -> str:
    if not any(character.isupper() for character in password):
        raise ValueError("Mật khẩu phải có ít nhất 1 ký tự viết hoa.")
    if not any(character.isdecimal() for character in password):
        raise ValueError("Mật khẩu phải có ít nhất 1 chữ số.")
    if not any(not character.isalnum() for character in password):
        raise ValueError("Mật khẩu phải có ít nhất 1 ký tự đặc biệt.")
    return password

def validate_confirm_password(password: str, confirm_password: str) -> str:
    if password != confirm_password:
        raise ValueError("Mật khẩu không khớp.")
    return confirm_password

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    confirm_password: str = Field(min_length=6)
    full_name: str = Field(min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def email_to_lowercase(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, password: str) -> str:
        return validate_password_strength(password)
    
    @field_validator("confirm_password")
    @classmethod
    def confirm_password_must_be_equal_to_password(cls, confirm_password: str, info: ValidationInfo) -> str:
        password = info.data.get("password")
        # If password failed its own validation it is absent from info.data,
        # so there is nothing to compare against here.
        if password is None:
            return confirm_password
        return validate_confirm_password(password, confirm_password)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def email_to_lowercase(cls, value: str) -> str:
        return value.strip().lower()


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)

    @field_validator("new_password")
    @classmethod
    def new_password_must_be_strong(cls, password: str) -> str:
        return validate_password_strength(password)


class UpgradePlanResponse(BaseModel):
    user_id: uuid.UUID
    plan: str
    message: str


class AvatarUploadResponse(BaseModel):
    content_type: str
    message: str = "Cập nhật ảnh đại diện thành công."


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    plan: str = "standard"
    user_id: uuid.UUID


class UserResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    plan: str = "standard"
    has_avatar: bool = False
    created_at: datetime
