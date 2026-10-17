import pytest

from app.models import Organization, User, AuditEvent
from app.routers.audit import append_audit
from app.security import sha256_hex


import uuid as _uuid
def _org_user(db):
    org = Organization(name="ACME", country="US", base_currency="USD", timezone="UTC", locale="en-US")
    db.add(org)
    db.commit()
    user = User(email=f"{_uuid.uuid4()}@b.com", password_hash="x" * 20, first_name="A")
    user.organization_id = org.id
    db.add(user)
    db.commit()
    return org, user


def test_audit_chain_verifies(db):
    org, user = _org_user(db)
    append_audit(db, org.id, "agent", "read", "a", "b")
    append_audit(db, org.id, "agent", "draft", "a", "c")
    events = db.query(AuditEvent).order_by(AuditEvent.timestamp.asc()).all()
    assert len(events) == 2
    assert events[0].prev_hash == "0" * 64
    assert events[1].prev_hash == events[0].hash


def test_tamper_detection(db):
    org, user = _org_user(db)
    append_audit(db, org.id, "agent", "read", "a", "b")
    ev = db.query(AuditEvent).first()
    ev.output_hash = "tampered"
    db.commit()
    events = db.query(AuditEvent).order_by(AuditEvent.timestamp.asc()).all()
    # recompute the hash from the (now tampered) fields and detect mismatch
    from app.routers.audit import sha256_hex as _sha
    computed = _sha(
        f"{events[0].id}{events[0].timestamp.isoformat()}{events[0].actor}{events[0].action}"
        f"{events[0].input_hash}{events[0].output_hash}{events[0].prev_hash}"
    )
    assert computed != events[0].hash
