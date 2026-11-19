"""SQLAlchemy engine, SQLite WAL configuration, and request session lifecycle."""

from __future__ import annotations

from collections.abc import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all LOOMOS ORM models."""


def _configure_sqlite_pragmas(engine: Engine) -> None:
    """Enable WAL journaling and strict foreign key enforcement on SQLite."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.close()


def build_engine(database_url: str | None = None) -> Engine:
    """Create a configured SQLAlchemy engine for SQLite or PostgreSQL."""
    settings = get_settings()
    url = database_url or f"sqlite:///{settings.db_path.as_posix()}"
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    eng = create_engine(url, connect_args=connect_args, future=True)
    if url.startswith("sqlite"):
        _configure_sqlite_pragmas(eng)
    return eng


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a scoped database session per FastAPI request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
