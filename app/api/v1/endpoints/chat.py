import json
import uuid
from datetime import UTC, datetime
from typing import Annotated

from cryptography.exceptions import InvalidTag
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import select

from app.core.crypto import (
    decrypt_aes_gcm,
    decrypt_server_secret,
    derive_key_hkdf,
    derive_shared_secret,
    encrypt_aes_gcm,
    encrypt_server_secret,
    generate_salt,
    get_server_x25519_keypair,
)
from app.core.database import SessionDep
from app.core.response import StandardResponse, success_response
from app.core.security import get_current_user
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.schemas.chat import (
    ChatMessageItem,
    ChatSessionItem,
    HandshakeRequest,
    HandshakeResponse,
    MessageResponse,
    SendMessageRequest,
    UpdateSessionTitleRequest,
    UserSaltResponse,
)
from app.services.gemini_service import GeminiService

router = APIRouter(prefix="/chat", tags=["Chatbot AI E2E"])


@router.get(
    "/user-salt",
    response_model=StandardResponse[UserSaltResponse],
    summary="Lấy User Salt và Public Key của máy chủ",
)
def get_user_salt(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
) -> StandardResponse[UserSaltResponse]:
    """Trả về encryption_salt của người dùng để dẫn xuất User Master Key và Public Key của server."""
    if not current_user.encryption_salt:
        current_user.encryption_salt = generate_salt()
        session.add(current_user)
        session.commit()
        session.refresh(current_user)

    _, server_pub_b64 = get_server_x25519_keypair()
    return success_response(
        request=request,
        message="Lấy salt và server public key thành công",
        data=UserSaltResponse(
            encryption_salt=current_user.encryption_salt,
            server_public_key=server_pub_b64,
        ),
    )


@router.post(
    "/handshake",
    response_model=StandardResponse[HandshakeResponse],
    summary="Khởi tạo phiên chat và bắt tay trao đổi khóa ECDH",
)
def handshake(
    request: Request,
    body: HandshakeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
) -> StandardResponse[HandshakeResponse]:
    """Tạo phiên chat mới, tính toán khóa phiên K_session từ ECDH và bọc kép (Dual-Envelope) lưu trữ."""
    server_priv, server_pub_b64 = get_server_x25519_keypair()

    try:
        shared_secret = derive_shared_secret(server_priv, body.client_public_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Khóa client_public_key không hợp lệ: {str(exc)}",
        ) from exc

    k_session = derive_key_hkdf(
        shared_secret=shared_secret,
        salt=b"traffic-chat-session",
        info=b"session-symmetric-key",
        length=32,
    )

    # Server bọc khóa phiên bằng Server Master Key để giải mã tạm trong RAM sau này
    enc_key_server, nonce_key_server = encrypt_server_secret(k_session)

    chat_session = ChatSession(
        user_id=current_user.user_id,
        title_encrypted=body.title_encrypted,
        title_nonce=body.title_nonce,
        session_key_enc_user=body.session_key_enc_user,
        session_key_nonce_user=body.session_key_nonce_user,
        session_key_enc_server=enc_key_server,
        session_key_nonce_server=nonce_key_server,
    )
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)

    return success_response(
        request=request,
        message="Khởi tạo phiên chat thành công",
        data=HandshakeResponse(
            session_id=chat_session.id,
            server_public_key=server_pub_b64,
        ),
    )


@router.post(
    "/message",
    response_model=StandardResponse[MessageResponse],
    summary="Gửi tin nhắn mã hóa và nhận phản hồi từ Gemini AI",
)
async def send_message(
    request: Request,
    body: SendMessageRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
) -> StandardResponse[MessageResponse]:
    """Giải mã tin nhắn trong RAM, gọi Gemini API đa lượt, mã hóa câu trả lời và lưu trữ dạng ciphertext."""
    chat_session = session.exec(
        select(ChatSession).where(
            ChatSession.id == body.session_id,
            ChatSession.user_id == current_user.user_id,
        )
    ).first()

    if not chat_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên chat không tồn tại hoặc bạn không có quyền truy cập.",
        )

    # Giải mã K_session trong RAM
    k_session = decrypt_server_secret(
        chat_session.session_key_enc_server,
        chat_session.session_key_nonce_server,
    )

    # Giải mã tin nhắn người dùng gửi lên
    try:
        user_pt_bytes = decrypt_aes_gcm(k_session, body.ciphertext, body.nonce)
        user_payload = json.loads(user_pt_bytes.decode("utf-8"))
        user_content = user_payload.get("content", "")
    except (InvalidTag, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể giải mã tin nhắn: Dữ liệu bị hỏng hoặc sai khóa (InvalidTag).",
        ) from exc

    # Lưu tin nhắn người dùng (chỉ lưu ciphertext + nonce vào DB)
    user_msg = ChatMessage(
        session_id=chat_session.id,
        role="user",
        ciphertext=body.ciphertext,
        nonce=body.nonce,
    )
    session.add(user_msg)
    session.commit()

    # Nạp lịch sử các lượt hội thoại gần nhất (tối đa 10 tin nhắn) để giữ context cho Gemini
    past_messages = session.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_session.id)
        .order_by(ChatMessage.created_at.asc())
    ).all()

    contents: list[dict] = []
    for msg in past_messages[-10:]:
        try:
            pt = decrypt_aes_gcm(k_session, msg.ciphertext, msg.nonce)
            txt = json.loads(pt.decode("utf-8")).get("content", "")
            contents.append({
                "role": msg.role,
                "parts": [{"text": txt}],
            })
        except Exception:
            continue

    if not contents:
        contents = [{"role": "user", "parts": [{"text": user_content}]}]

    # Gọi Google Gemini API
    gemini_service = GeminiService()
    system_instruction = (
        "Bạn là trợ lý AI thông minh, nhiệt tình và thân thiện. "
        "Hãy phản hồi ngắn gọn, rõ ràng và hữu ích bằng tiếng Việt."
    )
    ai_reply_text = await gemini_service.generate_response(
        contents=contents,
        system_instruction=system_instruction,
    )

    # Mã hóa phản hồi của AI bằng AES-256-GCM
    reply_payload = {
        "content": ai_reply_text,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    reply_pt_bytes = json.dumps(reply_payload).encode("utf-8")
    reply_ct, reply_nonce = encrypt_aes_gcm(k_session, reply_pt_bytes)

    # Lưu phản hồi AI vào DB (chỉ lưu ciphertext + nonce)
    ai_msg = ChatMessage(
        session_id=chat_session.id,
        role="model",
        ciphertext=reply_ct,
        nonce=reply_nonce,
    )
    chat_session.updated_at = datetime.now(UTC)
    session.add(ai_msg)
    session.add(chat_session)
    session.commit()

    return success_response(
        request=request,
        message="Nhận phản hồi từ AI thành công",
        data=MessageResponse(
            session_id=chat_session.id,
            ciphertext=reply_ct,
            nonce=reply_nonce,
        ),
    )


@router.get(
    "/sessions",
    response_model=StandardResponse[list[ChatSessionItem]],
    summary="Lấy danh sách các phiên chat của người dùng",
)
def list_sessions(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
) -> StandardResponse[list[ChatSessionItem]]:
    """Trả về danh sách các phiên chat cùng session_key_enc_user để client giải mã trên bất kỳ thiết bị nào."""
    sessions = session.exec(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.user_id)
        .order_by(ChatSession.updated_at.desc())
    ).all()

    items = [
        ChatSessionItem(
            id=s.id,
            title_encrypted=s.title_encrypted,
            title_nonce=s.title_nonce,
            session_key_enc_user=s.session_key_enc_user,
            session_key_nonce_user=s.session_key_nonce_user,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]

    return success_response(
        request=request,
        message="Lấy danh sách phiên chat thành công",
        data=items,
    )


@router.patch(
    "/sessions/{session_id}",
    response_model=StandardResponse[ChatSessionItem],
    summary="Cập nhật tiêu đề mã hóa của phiên chat",
)
def update_session_title(
    request: Request,
    session_id: uuid.UUID,
    body: UpdateSessionTitleRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
) -> StandardResponse[ChatSessionItem]:
    """Cập nhật title_encrypted và title_nonce cho phiên chat."""
    chat_session = session.exec(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.user_id,
        )
    ).first()

    if not chat_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên chat không tồn tại hoặc bạn không có quyền cập nhật.",
        )

    if body.title_encrypted is not None:
        chat_session.title_encrypted = body.title_encrypted
        chat_session.title_nonce = body.title_nonce
        chat_session.updated_at = datetime.now(UTC)
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)

    return success_response(
        request=request,
        message="Cập nhật tiêu đề phiên chat thành công",
        data=ChatSessionItem(
            id=chat_session.id,
            title_encrypted=chat_session.title_encrypted,
            title_nonce=chat_session.title_nonce,
            session_key_enc_user=chat_session.session_key_enc_user,
            session_key_nonce_user=chat_session.session_key_nonce_user,
            created_at=chat_session.created_at,
            updated_at=chat_session.updated_at,
        ),
    )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=StandardResponse[list[ChatMessageItem]],
    summary="Lấy lịch sử tin nhắn mã hóa của phiên chat",
)
def get_session_messages(
    request: Request,
    session_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
) -> StandardResponse[list[ChatMessageItem]]:
    """Trả về danh sách ciphertext tin nhắn của phiên để client tự giải mã."""
    chat_session = session.exec(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.user_id,
        )
    ).first()

    if not chat_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên chat không tồn tại hoặc bạn không có quyền xem.",
        )

    messages = session.exec(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    ).all()

    items = [
        ChatMessageItem(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            ciphertext=m.ciphertext,
            nonce=m.nonce,
            created_at=m.created_at,
        )
        for m in messages
    ]

    return success_response(
        request=request,
        message="Lấy lịch sử tin nhắn thành công",
        data=items,
    )


@router.delete(
    "/sessions/{session_id}",
    response_model=StandardResponse[dict],
    summary="Xóa phiên chat",
)
def delete_session(
    request: Request,
    session_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
) -> StandardResponse[dict]:
    """Xóa phiên chat và toàn bộ tin nhắn liên quan (cascade)."""
    chat_session = session.exec(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.user_id,
        )
    ).first()

    if not chat_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phiên chat không tồn tại hoặc bạn không có quyền xóa.",
        )

    # Delete all messages in session
    messages = session.exec(select(ChatMessage).where(ChatMessage.session_id == session_id)).all()
    for m in messages:
        session.delete(m)

    session.delete(chat_session)
    session.commit()

    return success_response(
        request=request,
        message="Xóa phiên chat thành công",
        data={"deleted_session_id": str(session_id)},
    )
