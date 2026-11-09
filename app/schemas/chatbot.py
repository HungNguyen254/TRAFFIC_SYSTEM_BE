from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    session_id: str | None = None
    hour_of_day: int | None = Field(default=None, ge=0, le=23)


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[dict] | None = None
    suggested_routes: dict | None = None
