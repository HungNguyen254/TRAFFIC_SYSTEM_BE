from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.database import SessionDep
from app.core.limiter import limiter
from app.core.response import StandardResponse, success_response
from app.core.security import get_optional_user
from app.models.user import User
from app.schemas.chatbot import ChatRequest, ChatResponse
from app.services.chatbot_service import ChatbotService

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.post(
    "/chat",
    response_model=StandardResponse[ChatResponse],
    status_code=status.HTTP_200_OK,
    summary="Hỏi đáp thông minh với Trợ lý Giao thông AI",
)
@limiter.limit("10/minute")
def chat_with_assistant(
    request: Request,
    payload: ChatRequest,
    session: SessionDep,
    current_user: Annotated[User | None, Depends(get_optional_user)],
):
    response = ChatbotService.process_chat(session, payload, current_user)
    return success_response(request=request, message="Phản hồi từ Trợ lý AI", data=response)
