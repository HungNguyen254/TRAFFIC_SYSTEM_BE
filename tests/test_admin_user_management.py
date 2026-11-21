import uuid

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.exceptions import BadRequestException
from app.models.chat import ChatSession
from app.models.user import User
from app.schemas.admin_user import AdminUserUpdate
from app.services.admin_user_service import AdminUserService


def create_test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def create_user(session, email, role="user"):
    user = User(
        email=email,
        full_name=email.split("@", maxsplit=1)[0],
        password_hash="test-password-hash",
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_admin_user_search_updates_user_and_revokes_existing_tokens():
    engine = create_test_engine()
    with Session(engine) as session:
        admin = create_user(session, "admin@example.com", role="admin")
        user = create_user(session, "person@example.com")

        result = AdminUserService.list_users(session, "PERSON")
        assert [item.user_id for item in result.users] == [user.user_id]

        old_token_version = user.token_version
        updated = AdminUserService.update_user(
            session,
            user.user_id,
            AdminUserUpdate(
                full_name="Updated Person",
                email="updated@example.com",
                role="admin",
            ),
            admin,
        )
        session.refresh(user)
        assert updated.email == "updated@example.com"
        assert updated.full_name == "Updated Person"
        assert updated.role == "admin"
        assert user.token_version == old_token_version + 1


def test_admin_user_cannot_remove_the_last_admin_or_self():
    engine = create_test_engine()
    with Session(engine) as session:
        admin = create_user(session, "admin@example.com", role="admin")

        try:
            AdminUserService.update_user(
                session,
                admin.user_id,
                AdminUserUpdate(
                    full_name=admin.full_name,
                    email=admin.email,
                    role="user",
                ),
                admin,
            )
        except BadRequestException as error:
            assert error.error_code == "CANNOT_DEMOTE_SELF"
        else:
            raise AssertionError("Expected self-demotion to be rejected")

        try:
            AdminUserService.delete_user(session, admin.user_id, admin)
        except BadRequestException as error:
            assert error.error_code == "CANNOT_DELETE_SELF"
        else:
            raise AssertionError("Expected deleting the current admin to be rejected")

        assert session.get(User, admin.user_id) is not None


def test_deleting_user_removes_their_chat_sessions():
    engine = create_test_engine()
    with Session(engine) as session:
        admin = create_user(session, "admin@example.com", role="admin")
        user = create_user(session, "person@example.com")
        chat_session = ChatSession(
            id=uuid.uuid4(),
            user_id=user.user_id,
            session_key_enc_user="encrypted",
            session_key_nonce_user="nonce",
            session_key_enc_server="encrypted",
            session_key_nonce_server="nonce",
        )
        session.add(chat_session)
        session.commit()

        AdminUserService.delete_user(session, user.user_id, admin)

        assert session.get(User, user.user_id) is None
        assert session.exec(
            select(ChatSession).where(ChatSession.user_id == user.user_id)
        ).all() == []
