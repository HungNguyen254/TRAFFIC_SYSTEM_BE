import uuid
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.user import User
from app.models.chat import ChatSession, ChatMessage

def test_user_has_encryption_salt():
    user = User(
        email="test_crypto@example.com",
        password_hash="fakehash",
        full_name="Crypto User",
    )
    assert user.encryption_salt is not None
    assert len(user.encryption_salt) > 10

def test_chat_models_database_roundtrip():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            email="chat_user@example.com",
            password_hash="fakehash",
            full_name="Chat User",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        chat_session = ChatSession(
            user_id=user.user_id,
            title_encrypted="enc_title_b64",
            title_nonce="nonce_title_b64",
            session_key_enc_user="enc_key_user_b64",
            session_key_nonce_user="nonce_user_b64",
            session_key_enc_server="enc_key_server_b64",
            session_key_nonce_server="nonce_server_b64",
        )
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)

        msg1 = ChatMessage(
            session_id=chat_session.id,
            role="user",
            ciphertext="msg_user_b64",
            nonce="nonce_msg1_b64",
        )
        msg2 = ChatMessage(
            session_id=chat_session.id,
            role="model",
            ciphertext="msg_model_b64",
            nonce="nonce_msg2_b64",
        )
        session.add(msg1)
        session.add(msg2)
        session.commit()

        # Query back
        messages = session.exec(
            select(ChatMessage).where(ChatMessage.session_id == chat_session.id)
        ).all()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "model"
