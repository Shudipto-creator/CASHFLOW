"""Hash-chained audit log (section 12.6)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app import models


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def _hash(fields: dict, prev_hash: str) -> str:
    payload = {k: v for k, v in fields.items() if k != "hash"}
    payload["prev_hash"] = prev_hash
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def last_event(db: Session, org_id: Optional[str]) -> Optional[models.AuditEvent]:
    q = db.query(models.AuditEvent)
    if org_id is not None:
        q = q.filter(models.AuditEvent.org_id == org_id)
    return q.order_by(models.AuditEvent.seq.desc()).first()


def next_seq(db: Session, org_id: Optional[str]) -> int:
    row = last_event(db, org_id)
    return (row.seq + 1) if row else 1


def write_event(
    db: Session,
    *,
    org_id: Optional[str],
    actor_type: str,
    actor_id: str,
    action: str,
    summary: str,
    input_hash: str,
    output_hash: str,
) -> models.AuditEvent:
    prev = last_event(db, org_id)
    prev_hash = prev.hash if prev else "0" * 64
    seq = (prev.seq + 1) if prev else 1
    fields = {
        "org_id": org_id,
        "seq": seq,
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor_type": actor_type,
        "actor_id": actor_id,
        "action": action,
        "summary": summary,
        "input_hash": input_hash,
        "output_hash": output_hash,
    }
    event = models.AuditEvent(
        org_id=org_id,
        seq=seq,
        ts=datetime.now(timezone.utc),
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        summary=summary,
        input_hash=input_hash,
        output_hash=output_hash,
        prev_hash=prev_hash,
        hash=_hash(fields, prev_hash),
    )
    db.add(event)
    db.flush()
    return event


def verify_chain(db: Session, org_id: Optional[str] = None) -> tuple[bool, Optional[int]]:
    """Returns (ok, first_broken_seq)."""
    q = db.query(models.AuditEvent)
    if org_id is not None:
        q = q.filter(models.AuditEvent.org_id == org_id)
    events = q.order_by(models.AuditEvent.seq.asc()).all()
    prev_hash = "0" * 64
    for event in events:
        fields = {
            "org_id": event.org_id,
            "seq": event.seq,
            "ts": event.ts.isoformat(),
            "actor_type": event.actor_type,
            "actor_id": event.actor_id,
            "action": event.action,
            "summary": event.summary,
            "input_hash": event.input_hash,
            "output_hash": event.output_hash,
        }
        expected = _hash(fields, prev_hash)
        if (
            event.seq != (events.index(event) + 1)
            or event.prev_hash != prev_hash
            or event.hash != expected
        ):
            return False, event.seq
        prev_hash = event.hash
    return True, None
