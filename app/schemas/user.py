from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.schemas.observation import serialize_utc_z


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str
    password: str = Field(min_length=6, max_length=128)


class UserRead(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def serialize_created_at(self, v: datetime) -> str:
        return serialize_utc_z(v)


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
