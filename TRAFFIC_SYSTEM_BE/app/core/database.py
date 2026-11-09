import logging
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401  # register table models before create_all()
from app.core.config import settings

logger = logging.getLogger(__name__)

# Supabase requires TLS. Poolers already open a TLS channel per client, so the
# smaller pool keeps us well below the server-side connection limit.
_POOL_SIZE = 5
_MAX_OVERFLOW = 5


def _build_database_url(raw_url: str) -> str:
    """Normalize the URL and pin the psycopg (v3) driver explicitly."""
    url = raw_url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    url = url.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")
    for prefix in ("postgresql+psycopg2://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix) :]
            break
    return url


def _build_connect_args(url: str) -> dict[str, object]:
    """pgbouncer (transaction pooling) needs prepared statements disabled."""
    connect_args: dict[str, object] = {}
    if ":6543" in url or "pooler.supabase.com" in url:
        connect_args["prepare_threshold"] = None
    if "sslmode=" not in url:
        connect_args["sslmode"] = "require"
    return connect_args


db_url = _build_database_url(settings.DATABASE_URL)

engine = create_engine(
    db_url,
    echo=False,  # never log SQL payloads; flip manually when debugging
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=_POOL_SIZE,
    max_overflow=_MAX_OVERFLOW,
    connect_args=_build_connect_args(db_url),
)


def init_db() -> None:
    """Create all tables defined in SQLModel metadata (development only).

    Schema changes in production go through migrations, so DDL is skipped
    unless ``DEBUG`` is enabled.
    """
    if not settings.DEBUG:
        logger.info("DEBUG is off: skipping create_all(), use migrations.")
        return
    SQLModel.metadata.create_all(engine)


def check_db_connection() -> None:
    """Raise if the connection to Supabase PostgreSQL is not alive."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def get_session() -> Generator[Session, None, None]:
    """Dependency for providing a SQLModel Session per request."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
