import logging
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
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


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """Enable foreign key constraints for SQLite connections on the application engine."""
    if "sqlite" in db_url:
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        except Exception:  # noqa: BLE001, S110
            pass


def _apply_schema_patches(target_engine=None) -> None:
    """Ensure missing columns in existing tables are added if tables existed before schema updates."""
    from sqlalchemy import inspect

    from app.core.crypto import generate_salt

    db_engine = target_engine or engine
    try:
        inspector = inspect(db_engine)
        if inspector.has_table("users"):
            user_cols = {c["name"] for c in inspector.get_columns("users")}
            if "plan" not in user_cols:
                logger.info("Applying schema patch: adding missing 'plan' column to 'users' table...")
                with db_engine.begin() as conn:
                    conn.execute(
                        text("ALTER TABLE users ADD COLUMN plan VARCHAR(20) DEFAULT 'standard' NOT NULL")
                    )
                logger.info("Schema patch for 'users.plan' applied successfully.")
            if "plan_updated_at" not in user_cols:
                with db_engine.begin() as conn:
                    conn.execute(
                        text("ALTER TABLE users ADD COLUMN plan_updated_at TIMESTAMP WITH TIME ZONE")
                    )
                logger.info("Schema patch for 'users.plan_updated_at' applied successfully.")
            if "encryption_salt" not in user_cols:
                logger.info("Applying schema patch: adding missing 'encryption_salt' to 'users' table...")
                with db_engine.begin() as conn:
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
            if "avatar_content_type" not in user_cols:
                logger.info("Applying schema patch: adding missing 'avatar_content_type' to 'users' table...")
                with db_engine.begin() as conn:
                    conn.execute(
                        text("ALTER TABLE users ADD COLUMN avatar_content_type VARCHAR(32)")
                    )
                logger.info("Schema patch for 'users.avatar_content_type' applied successfully.")
            if "avatar_data" not in user_cols:
                logger.info("Applying schema patch: adding missing 'avatar_data' to 'users' table...")
                blob_type = "BYTEA" if "postgresql" in str(db_engine.url) else "BLOB"
                with db_engine.begin() as conn:
                    conn.execute(
                        text(f"ALTER TABLE users ADD COLUMN avatar_data {blob_type}")
                    )
                logger.info("Schema patch for 'users.avatar_data' applied successfully.")
            if "avatar_updated_at" not in user_cols:
                logger.info("Applying schema patch: adding missing 'avatar_updated_at' to 'users' table...")
                ts_type = "TIMESTAMP WITH TIME ZONE" if "postgresql" in str(db_engine.url) else "DATETIME"
                with db_engine.begin() as conn:
                    conn.execute(
                        text(f"ALTER TABLE users ADD COLUMN avatar_updated_at {ts_type}")
                    )
                logger.info("Schema patch for 'users.avatar_updated_at' applied successfully.")
            if inspector.has_table("user_avatars"):
                logger.info("Applying schema patch: migrating existing avatars from 'user_avatars' to 'users'...")
                with db_engine.begin() as conn:
                    conn.execute(
                        text("""
                            UPDATE users
                            SET avatar_content_type = (SELECT content_type FROM user_avatars WHERE user_avatars.user_id = users.user_id),
                                avatar_data = (SELECT image_data FROM user_avatars WHERE user_avatars.user_id = users.user_id),
                                avatar_updated_at = (SELECT updated_at FROM user_avatars WHERE user_avatars.user_id = users.user_id)
                            WHERE user_id IN (SELECT user_id FROM user_avatars)
                              AND (users.avatar_data IS NULL)
                        """)
                    )
                    conn.execute(text("DROP TABLE user_avatars"))
                logger.info("Avatar migration completed and old user_avatars table dropped.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Schema patch check encountered an error: %s", exc)


def init_db() -> None:
    """Create all database tables defined in SQLModel metadata and run minor schema patches."""
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
