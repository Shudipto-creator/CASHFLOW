"""Server-side conversation memory for the FINN CFO chat.

The chat endpoint used to receive only the latest message: the transcript lived
in the browser and the model never saw it, so a follow-up such as "and last
month?" or "上个月呢？" was interpreted from scratch.  This module keeps the
transcript in the application database (``cfone.db``) and turns it into

* prompt context for the intent model, and
* the small amount of state needed to resolve short follow-ups.

Everything here is scoped by ``user_id`` *and* ``conversation_id``.  A client
may know a conversation id, but it can never read or extend another user's
transcript, because every query filters on the authenticated user as well.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from app import models

#: How many rows we load for a turn.  Enough for context, bounded for tokens.
MAX_HISTORY_MESSAGES = 40
#: How many turns are rendered into an LLM prompt.
PROMPT_HISTORY_MESSAGES = 10
PROMPT_HISTORY_CHARS = 5000

_CJK = re.compile(r"[\u4e00-\u9fff]")
_CONVERSATION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_PERIOD_PATTERNS = (
    ("last_month", re.compile(r"\b(?:last|previous)\s+month\b|上个?月|上月", re.IGNORECASE)),
    ("this_month", re.compile(r"\bthis\s+month\b|本月|这个月", re.IGNORECASE)),
    ("this_year", re.compile(r"\bthis\s+year\b|今年", re.IGNORECASE)),
)

_FOLLOW_UP_PATTERNS = (
    re.compile(r"^\s*(?:and|also|then|so|what about|how about|same|what else)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:那|那么|还有|同样|也|再|另外)"),
    re.compile(r"(?:呢|怎么样|如何)\s*[?？]?\s*$"),
)


def detect_language(*texts: Optional[str]) -> str:
    """Return ``"zh"`` when any supplied text contains CJK, else ``"en"``."""
    for text in texts:
        if text and _CJK.search(text):
            return "zh"
    return "en"


def new_conversation_id() -> str:
    return f"cfo_{uuid.uuid4().hex}"


def normalize_conversation_id(value: Optional[str]) -> Optional[str]:
    """Accept a client conversation id only when it is short and opaque."""
    if not value:
        return None
    candidate = str(value).strip()
    return candidate if _CONVERSATION_ID.match(candidate) else None


def is_follow_up(message: str) -> bool:
    """True for short continuations like "and last month?" / "上个月呢？"."""
    text = (message or "").strip()
    if not text or len(text) > 120:
        return False
    return any(pattern.search(text) for pattern in _FOLLOW_UP_PATTERNS)


def period_from_message(message: str) -> Optional[str]:
    """Return the period name explicitly mentioned in ``message``, if any."""
    text = (message or "").strip()
    for name, pattern in _PERIOD_PATTERNS:
        if pattern.search(text):
            return name
    return None


def _to_dict(row: models.CfoChatMessage) -> dict[str, Any]:
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "role": row.role,
        "content": row.content,
        "intent": row.intent,
        "metadata": row.message_metadata or {},
        "created_at": row.created_at,
    }


def append_message(
    db: Session,
    *,
    user_id: str,
    conversation_id: str,
    role: str,
    content: str,
    intent: Optional[str] = None,
    message_metadata: Optional[dict[str, Any]] = None,
) -> models.CfoChatMessage:
    """Persist one chat turn and return the stored row."""
    row = models.CfoChatMessage(
        conversation_id=conversation_id,
        user_id=str(user_id),
        role=role,
        content=content,
        intent=intent,
        message_metadata=message_metadata or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def load_history(
    db: Session,
    *,
    user_id: str,
    conversation_id: str,
    limit: int = MAX_HISTORY_MESSAGES,
) -> list[dict[str, Any]]:
    """Return the most recent turns in chronological order.

    The authenticated ``user_id`` is always part of the filter, so reusing a
    conversation id from another account yields an empty history instead of a
    data leak.
    """
    rows = (
        db.query(models.CfoChatMessage)
        .filter(
            models.CfoChatMessage.user_id == str(user_id),
            models.CfoChatMessage.conversation_id == conversation_id,
        )
        .order_by(models.CfoChatMessage.id.desc())
        .limit(max(1, int(limit)))
        .all()
    )
    return [_to_dict(row) for row in reversed(rows)]


def load_conversation(
    db: Session,
    *,
    user_id: str,
    conversation_id: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return a whole conversation for display, oldest first."""
    rows = (
        db.query(models.CfoChatMessage)
        .filter(
            models.CfoChatMessage.user_id == str(user_id),
            models.CfoChatMessage.conversation_id == conversation_id,
        )
        .order_by(models.CfoChatMessage.id.asc())
        .limit(max(1, int(limit)))
        .all()
    )
    return [_to_dict(row) for row in rows]


def latest_conversation_id(db: Session, user_id: str) -> Optional[str]:
    row = (
        db.query(models.CfoChatMessage)
        .filter(models.CfoChatMessage.user_id == str(user_id))
        .order_by(models.CfoChatMessage.id.desc())
        .first()
    )
    return row.conversation_id if row else None


def delete_conversation(db: Session, *, user_id: str, conversation_id: str) -> int:
    deleted = (
        db.query(models.CfoChatMessage)
        .filter(
            models.CfoChatMessage.user_id == str(user_id),
            models.CfoChatMessage.conversation_id == conversation_id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(deleted or 0)


def history_for_prompt(
    history: Iterable[dict[str, Any]],
    *,
    max_messages: int = PROMPT_HISTORY_MESSAGES,
    max_chars: int = PROMPT_HISTORY_CHARS,
) -> str:
    """Render recent turns as compact prompt context (oldest first).

    Older turns are dropped first so the most recent exchange always survives
    the character budget.
    """
    items = [item for item in history if item.get("role") in {"user", "assistant"}]
    items = items[-max_messages:]

    # Trim from the front (oldest) until the block fits the budget.
    while items and sum(len(item.get("content") or "") for item in items) > max_chars:
        items = items[1:]

    lines: list[str] = []
    for item in items:
        speaker = "User" if item["role"] == "user" else "FINN"
        content = (item.get("content") or "").strip()
        if content:
            lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def last_topic(history: Iterable[dict[str, Any]]) -> Optional[str]:
    """Return the topic of the most recent assistant turn, if recorded."""
    for item in reversed(list(history)):
        if item.get("role") == "assistant" and item.get("intent"):
            return str(item["intent"])
    return None


def last_message_metadata(
    history: Iterable[dict[str, Any]],
    *,
    intent: Optional[str] = None,
) -> dict[str, Any]:
    """Return metadata from the most recent matching assistant turn."""
    for item in reversed(list(history)):
        if item.get("role") != "assistant":
            continue
        if intent is not None and item.get("intent") != intent:
            continue
        metadata = item.get("metadata")
        return metadata if isinstance(metadata, dict) else {}
    return {}


__all__ = [
    "MAX_HISTORY_MESSAGES",
    "append_message",
    "delete_conversation",
    "detect_language",
    "history_for_prompt",
    "is_follow_up",
    "last_message_metadata",
    "last_topic",
    "latest_conversation_id",
    "load_conversation",
    "load_history",
    "new_conversation_id",
    "normalize_conversation_id",
    "period_from_message",
]
