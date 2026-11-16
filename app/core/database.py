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


def _apply_schema_patches() -> None:
    """Ensure missing columns in existing tables are added if tables existed before schema updates."""
    from sqlalchemy import inspect
    from app.core.crypto import generate_salt

    try:
        inspector = inspect(engine)
        if inspector.has_table("users"):
            user_cols = {c["name"] for c in inspector.get_columns("users")}
            if "encryption_salt" not in user_cols:
                logger.info("Applying schema patch: adding missing 'encryption_salt' to 'users' table...")
                with engine.begin() as conn:
                    conn.execute(
                        text("ALTER TABLE users ADD COLUMN encryption_salt VARCHAR(64)")
                    )
                    rows = conn.execute(
                        text("SELECT user_id FROM users WHERE encryption_salt IS NULL")
                    ).fetchall()
                    for r in rows:
                        conn.execute(
                            text("UPDATE users SET encryption_salt = :salt WHERE user_id = :uid"),
                            {"salt": generate_salt(), "uid": r[0]},
                        )
                logger.info("Schema patch for 'users.encryption_salt' applied successfully.")
    except Exception as exc:
        logger.warning("Schema patch check encountered an error: %s", exc)


def init_db() -> None:
    """Create all database tables defined in SQLModel metadata and run minor schema patches."""
    import app.models
    SQLModel.metadata.create_all(engine)
    _apply_schema_patches()


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
