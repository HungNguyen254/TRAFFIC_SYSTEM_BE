from sqlmodel import Session, select
from app.models.user import User, UserRole


def test_user_model_creation(session: Session):
    user = User(
        username="testadmin",
        email="admin@test.com",
        hashed_password="hashed_pw_placeholder",
        role=UserRole.ADMIN,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    assert user.id is not None
    assert user.username == "testadmin"
    assert user.email == "admin@test.com"
    assert user.role == UserRole.ADMIN
    assert user.is_active is True
    assert user.created_at is not None
