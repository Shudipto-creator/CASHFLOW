"""Database setup and session management for CASHFLOW."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import get_settings

settings = get_settings()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_db_url = settings.database_url
if _db_url.startswith("sqlite:///."):
    _abs_db_path = os.path.join(PROJECT_ROOT, _db_url.replace("sqlite:///./", "").replace("sqlite:///.", ""))
    _db_url = f"sqlite:///{_abs_db_path}"

engine = create_engine(
    _db_url,
    connect_args={"check_same_thread": False} if _db_url.startswith("sqlite") else {},
    echo=settings.debug,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import app.models  # noqa: F401  register models
    Base.metadata.create_all(bind=engine)
