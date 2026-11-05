from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args=connect_args,
)


def get_session() -> Generator[Session]:
    """Dependency for providing a SQLModel Session per request."""
    with Session(engine) as session:
        yield session
