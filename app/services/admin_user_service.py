import uuid

from sqlalchemy import func
from sqlmodel import Session, delete, select

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.schemas.admin_user import AdminUserListResponse, AdminUserResponse, AdminUserUpdate


class AdminUserService:
    @staticmethod
    def list_users(session: Session, query: str = "") -> AdminUserListResponse:
        statement = select(User)
        normalized_query = query.strip()
        if normalized_query:
            pattern = f"%{normalized_query}%"
            statement = statement.where(
                (User.email.ilike(pattern)) | (User.full_name.ilike(pattern))
            )
        users = session.exec(statement.order_by(User.created_at.desc()).limit(500)).all()
        return AdminUserListResponse(
            users=[
                AdminUserResponse(
                    user_id=user.user_id,
                    full_name=user.full_name,
                    email=user.email,
                    role=user.role,
                    created_at=user.created_at,
                )
                for user in users
            ]
        )

    @staticmethod
    def update_user(
        session: Session,
        user_id: uuid.UUID,
        payload: AdminUserUpdate,
        current_admin: User,
    ) -> AdminUserResponse:
        user = session.get(User, user_id)
        if user is None:
            raise NotFoundException(
                message=f"Không tìm thấy tài khoản có id {user_id}.",
                error_code="USER_NOT_FOUND",
                details={"user_id": str(user_id)},
            )

        duplicate = session.exec(
            select(User).where(
                func.lower(User.email) == str(payload.email).casefold(),
                User.user_id != user_id,
            )
        ).first()
        if duplicate:
            raise BadRequestException(
                message="Email này đã được sử dụng bởi tài khoản khác.",
                error_code="USER_EMAIL_DUPLICATED",
            )

        if (
            user.user_id == current_admin.user_id
            and payload.role != "admin"
        ):
            raise BadRequestException(
                message="Không thể tự hạ quyền quản trị viên đang đăng nhập.",
                error_code="CANNOT_DEMOTE_SELF",
            )

        if user.role == "admin" and payload.role != "admin":
            other_admin = session.exec(
                select(User.user_id)
                .where(User.role == "admin", User.user_id != user_id)
                .limit(1)
            ).first()
            if other_admin is None:
                raise BadRequestException(
                    message="Không thể hạ quyền quản trị viên cuối cùng.",
                    error_code="LAST_ADMIN_REQUIRED",
                )

        user.full_name = payload.full_name
        user.email = str(payload.email)
        user.role = payload.role
        user.token_version += 1
        session.add(user)
        session.commit()
        session.refresh(user)
        return AdminUserResponse(
            user_id=user.user_id,
            full_name=user.full_name,
            email=user.email,
            role=user.role,
            created_at=user.created_at,
        )

    @staticmethod
    def delete_user(
        session: Session, user_id: uuid.UUID, current_admin: User
    ) -> None:
        user = session.get(User, user_id)
        if user is None:
            raise NotFoundException(
                message=f"Không tìm thấy tài khoản có id {user_id}.",
                error_code="USER_NOT_FOUND",
                details={"user_id": str(user_id)},
            )

        if user.user_id == current_admin.user_id:
            raise BadRequestException(
                message="Không thể xóa tài khoản quản trị viên đang đăng nhập.",
                error_code="CANNOT_DELETE_SELF",
            )

        if user.role == "admin":
            other_admin = session.exec(
                select(User.user_id)
                .where(User.role == "admin", User.user_id != user_id)
                .limit(1)
            ).first()
            if other_admin is None:
                raise BadRequestException(
                    message="Không thể xóa quản trị viên cuối cùng.",
                    error_code="LAST_ADMIN_REQUIRED",
                )

        chat_session_ids = session.exec(
            select(ChatSession.id).where(ChatSession.user_id == user_id)
        ).all()
        if chat_session_ids:
            session.exec(
                delete(ChatMessage).where(
                    ChatMessage.session_id.in_(chat_session_ids)
                )
            )
            session.exec(
                delete(ChatSession).where(ChatSession.id.in_(chat_session_ids))
            )
        session.delete(user)
        session.commit()
