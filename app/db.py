"""Database engine, session and base for CASHFLOW."""

from __future__ import annotations

import os
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

_db_url = settings.database_url
connect_args = {}
if _db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    _db_url,
    connect_args=connect_args,
    echo=settings.debug,
    pool_pre_ping=True,
)

if _db_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Iterator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    import app.models  # noqa: F401  register all models

    Base.metadata.create_all(bind=engine)
