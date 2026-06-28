"""Engine + session management for the local SQLite database."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings
from .base import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _enable_sqlite_pragmas(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    # Concurrent sync writes from a thread pool can briefly collide; wait instead of erroring.
    cur.execute("PRAGMA busy_timeout=10000")
    cur.close()


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.db_url, future=True, connect_args={"check_same_thread": False}
        )
        event.listen(_engine, "connect", _enable_sqlite_pragmas)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def init_db() -> None:
    """Create all tables. (Alembic migrations are introduced once the schema stabilizes.)"""
    # Import models so they register on Base.metadata before create_all.
    from . import models  # noqa: F401

    get_engine()
    Base.metadata.create_all(get_engine())
    _lightweight_migrate()


# Columns added after a table first shipped. create_all() won't ALTER existing tables,
# so for SQLite we additively add missing columns in place (idempotent, data-preserving).
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "watchlists": {"sort_order": "INTEGER NOT NULL DEFAULT 0"},
    "watchlist_items": {"sort_order": "INTEGER NOT NULL DEFAULT 0"},
}


def _lightweight_migrate() -> None:
    eng = get_engine()
    with eng.begin() as conn:
        for table, cols in _ADDED_COLUMNS.items():
            existing = {
                row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            }
            for name, ddl in cols.items():
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


@contextmanager
def session_scope() -> Iterator[Session]:
    get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
