import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class UserSaltResponse(BaseModel):
    encryption_salt: str
    server_public_key: str


class HandshakeRequest(BaseModel):
    client_public_key: str = Field(description="Base64 encoded client X25519 public key")
    session_key_enc_user: str = Field(description="Base64 encoded session key encrypted with User Master Key")
    session_key_nonce_user: str = Field(description="Base64 encoded nonce for user encrypted session key")
    title_encrypted: str | None = None
    title_nonce: str | None = None


class HandshakeResponse(BaseModel):
    session_id: uuid.UUID
    server_public_key: str


class SendMessageRequest(BaseModel):
    session_id: uuid.UUID
    ciphertext: str = Field(description="Base64 encoded ciphertext of JSON payload")
    nonce: str = Field(description="Base64 encoded 12-byte nonce")


class MessageResponse(BaseModel):
    session_id: uuid.UUID
    ciphertext: str = Field(description="Base64 encoded AI response ciphertext")
    nonce: str = Field(description="Base64 encoded 12-byte nonce")


class UpdateSessionTitleRequest(BaseModel):
    title_encrypted: str | None = None
    title_nonce: str | None = None


class ChatSessionItem(BaseModel):
    id: uuid.UUID
    title_encrypted: str | None = None
    title_nonce: str | None = None
    session_key_enc_user: str
    session_key_nonce_user: str
    created_at: datetime
    updated_at: datetime


class ChatMessageItem(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    ciphertext: str
    nonce: str
    created_at: datetime
