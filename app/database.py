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
