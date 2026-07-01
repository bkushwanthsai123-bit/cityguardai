"""SQLAlchemy 2.x engine, session factory, and declarative base."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# SQLite needs check_same_thread disabled for FastAPI's threadpool usage.
_connect_args = (
    {"check_same_thread": False} if settings.DB_URL.startswith("sqlite") else {}
)

engine = create_engine(
    settings.DB_URL,
    connect_args=_connect_args,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def init_db() -> None:
    """Create all tables. Safe to call repeatedly (idempotent)."""
    # Import models so they register on Base.metadata before create_all.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """Lightweight, Alembic-free migration for added nullable columns.

    ``create_all`` never ALTERs an existing table, so columns added to a model
    after the DB was first created are missing on old SQLite files. Add them
    idempotently. Only supports SQLite (the app's default backend).
    """
    if not settings.DB_URL.startswith("sqlite"):
        return
    from sqlalchemy import text

    wanted = {"annotated_path": "VARCHAR"}
    with engine.begin() as conn:
        existing = {
            row[1]  # column name
            for row in conn.execute(text("PRAGMA table_info(incidents)"))
        }
        for name, coltype in wanted.items():
            if name not in existing:
                conn.execute(
                    text(f"ALTER TABLE incidents ADD COLUMN {name} {coltype}")
                )


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
