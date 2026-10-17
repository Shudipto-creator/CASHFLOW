import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ["DATABASE_URL"] = "sqlite:///./data/test_cf.db"
os.environ["SECRET_KEY"] = "x" * 32
os.environ["LLM_PROVIDER"] = "mock"

from app.config import get_settings

get_settings.cache_clear()

from app.database import Base, engine, init_db, SessionLocal
import app.models  # noqa: F401

init_db()


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    from app import models as m
    # reverse order to respect foreign keys
    session.query(m.AuditEvent).delete()
    session.query(m.User).delete()
    session.query(m.Organization).delete()
    session.commit()
    session.close()
