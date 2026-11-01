"""Database setup and session management"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
import os

settings = get_settings()

# Project root = parent of the 'app' package directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Create data directory if it doesn't exist
os.makedirs(os.path.join(PROJECT_ROOT, "data"), exist_ok=True)

# Resolve the database URL to an absolute path when using SQLite
_db_url = settings.database_url
if _db_url.startswith("sqlite:///."):
    _abs_db_path = os.path.join(PROJECT_ROOT, _db_url.replace("sqlite:///./", "").replace("sqlite:///.", ""))
    _db_url = f"sqlite:///{_abs_db_path}"

# Create SQLAlchemy engine
engine = create_engine(
    _db_url,
    connect_args={"check_same_thread": False},  # For SQLite
    echo=settings.debug,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    import app.models  # Import models to register them

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns():
    """Add newly introduced columns on existing SQLite databases."""
    if not str(engine.url).startswith("sqlite"):
        return

    from sqlalchemy import text

    # One-time rename of legacy "wilson_*" tables to "billflow_*"
    renames = [
        ("wilson_imports", "billflow_imports"),
        ("wilson_transactions", "billflow_transactions"),
    ]
    with engine.connect() as conn:
        for old, new in renames:
            old_exists = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"), {"n": old}
            ).fetchone()
            new_exists = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"), {"n": new}
            ).fetchone()
            if old_exists and not new_exists:
                conn.execute(text(f"ALTER TABLE {old} RENAME TO {new}"))
        conn.commit()

    alterations = [
        ("analyses", "processing_mode", "ALTER TABLE analyses ADD COLUMN processing_mode VARCHAR(20) DEFAULT 'aws'"),
        ("users", "role", "ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'"),
    ]

    with engine.connect() as conn:
        for table, column, ddl in alterations:
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            existing = {row[1] for row in rows}
            if column not in existing:
                conn.execute(text(ddl))
        conn.commit()
