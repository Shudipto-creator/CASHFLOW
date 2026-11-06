import asyncio
import re
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.routers import auth
from app.schemas import PasswordRecoveryComplete, PasswordRecoveryRequest
from app.services.password_recovery import PasswordRecoveryCodes, RecoveryCooldownError
from app.utils.auth import hash_password, verify_password


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _request_code(email, capsys):
    response = asyncio.run(auth.request_password_recovery(PasswordRecoveryRequest(email=email)))
    output = capsys.readouterr().out
    code = re.search(r"\): (\d{6})$", output)
    assert code
    assert code.group(1) not in str(response)
    return response["challenge_id"], code.group(1)


def test_password_recovery_changes_hash_and_code_is_single_use(db_session, capsys, monkeypatch):
    monkeypatch.setattr(auth, "password_recovery_codes", PasswordRecoveryCodes())
    monkeypatch.setattr(auth, "get_settings", lambda: SimpleNamespace(app_env="development"))
    old_password = "OldPass123"
    user = models.User(
        email="person@example.com",
        password_hash=hash_password(old_password),
        company_name="Person",
    )
    db_session.add(user)
    db_session.commit()

    challenge_id, code = _request_code(user.email, capsys)
    response = asyncio.run(
        auth.complete_password_recovery(
            PasswordRecoveryComplete(
                email=user.email,
                challenge_id=challenge_id,
                code=code,
                new_password="NewPass456",
            ),
            db_session,
        )
    )

    db_session.refresh(user)
    assert response["message"].startswith("Password updated.")
    assert verify_password("NewPass456", user.password_hash)
    assert not verify_password(old_password, user.password_hash)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            auth.complete_password_recovery(
                PasswordRecoveryComplete(
                    email=user.email,
                    challenge_id=challenge_id,
                    code=code,
                    new_password="OtherPass789",
                ),
                db_session,
            )
        )
    assert error.value.status_code == 400


def test_password_recovery_rejects_wrong_code_without_changing_password(
    db_session, capsys, monkeypatch
):
    monkeypatch.setattr(auth, "password_recovery_codes", PasswordRecoveryCodes())
    monkeypatch.setattr(auth, "get_settings", lambda: SimpleNamespace(app_env="development"))
    old_password = "OldPass123"
    user = models.User(
        email="person@example.com",
        password_hash=hash_password(old_password),
        company_name="Person",
    )
    db_session.add(user)
    db_session.commit()

    challenge_id, code = _request_code(user.email, capsys)
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            auth.complete_password_recovery(
                PasswordRecoveryComplete(
                    email=user.email,
                    challenge_id=challenge_id,
                    code="000000" if code != "000000" else "000001",
                    new_password="NewPass456",
                ),
                db_session,
            )
        )

    assert error.value.status_code == 400
    db_session.refresh(user)
    assert verify_password(old_password, user.password_hash)


def test_unknown_email_cannot_complete_password_recovery(db_session, capsys, monkeypatch):
    monkeypatch.setattr(auth, "password_recovery_codes", PasswordRecoveryCodes())
    monkeypatch.setattr(auth, "get_settings", lambda: SimpleNamespace(app_env="development"))
    challenge_id, code = _request_code("unknown@example.com", capsys)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            auth.complete_password_recovery(
                PasswordRecoveryComplete(
                    email="unknown@example.com",
                    challenge_id=challenge_id,
                    code=code,
                    new_password="NewPass456",
                ),
                db_session,
            )
        )

    assert error.value.status_code == 400
    assert error.value.detail == (
        "Could not complete password recovery. Check the email and code, then try again."
    )


def test_password_recovery_enforces_cooldown_and_attempt_limit(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("app.services.password_recovery.time.monotonic", lambda: now[0])
    monkeypatch.setattr("app.services.password_recovery.secrets.randbelow", lambda _: 123456)
    codes = PasswordRecoveryCodes()
    challenge_id = codes.issue("person@example.com")
    with pytest.raises(RecoveryCooldownError, match="Please wait"):
        codes.issue("person@example.com")

    assert not codes.verify("person@example.com", challenge_id, "000000")
    assert not codes.verify("person@example.com", challenge_id, "000000")
    assert not codes.verify("person@example.com", challenge_id, "000000")
    assert not codes.verify("person@example.com", challenge_id, "000000")

    now[0] += 61
    assert codes.issue("person@example.com")


def test_password_recovery_endpoint_is_disabled_outside_development(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: SimpleNamespace(app_env="production"))
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            auth.request_password_recovery(
                PasswordRecoveryRequest(email="person@example.com")
            )
        )
    assert error.value.status_code == 503


def test_password_recovery_requires_registration_password_strength():
    with pytest.raises(ValueError, match="uppercase"):
        PasswordRecoveryComplete(
            email="person@example.com",
            challenge_id="recovery-1",
            code="123456",
            new_password="weakpass1",
        )
