import logging
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_database_url(raw_url: str) -> str:
    url = raw_url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    url = url.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")
    return url


db_url = _build_database_url(settings.DATABASE_URL)

connect_args: dict[str, object] = {}
if ":6543" in db_url or "pooler.supabase.com" in db_url:
    connect_args["prepare_threshold"] = None
if "sqlite" in db_url:
    connect_args["check_same_thread"] = False

engine = create_engine(
    db_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args=connect_args,
)


def init_db() -> None:
    """Create all database tables defined in SQLModel metadata."""
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def check_db_connection() -> bool:
    """Check if connection to Supabase PostgreSQL is alive."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True


def get_session() -> Generator[Session]:
    """Dependency for providing a SQLModel Session per request."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
