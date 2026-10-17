"""Masking of sensitive values before they reach a model (section 13.4)."""

from __future__ import annotations

import re
from typing import Dict

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}\b")
ACCOUNT_RE = re.compile(r"\b\d{8,19}\b")
IBAN_RE = re.compile(r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4,}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
GOV_ID_RE = re.compile(r"\b[A-Z]{1,3}[- ]?\d{6,12}\b")


def _replacer(kind: str, index: int) -> str:
    return f"[{kind.upper()}_{index}]"


def mask_text(text: str) -> tuple[str, Dict[str, str]]:
    """Mask sensitive patterns. Returns (masked_text, map[token] -> original)."""
    if not text:
        return text, {}
    counter: Dict[str, int] = {}
    mapping: Dict[str, str] = {}

    def replace(match: re.Match, kind: str) -> str:
        original = match.group(0)
        counter[kind] = counter.get(kind, 0) + 1
        token = _replacer(kind, counter[kind])
        mapping[token] = original
        return token

    patterns = [
        (EMAIL_RE, "email"),
        (PHONE_RE, "phone"),
        (IBAN_RE, "iban"),
        (CARD_RE, "card"),
        (ACCOUNT_RE, "account"),
        (GOV_ID_RE, "id"),
    ]
    result = text
    for pattern, kind in patterns:
        result = pattern.sub(lambda m, k=kind: replace(m, k), result)
    return result, mapping


def restore_text(masked: str, mapping: Dict[str, str]) -> str:
    """Restore originals for display in the UI only."""
    result = masked
    for token, original in mapping.items():
        result = result.replace(token, original)
    return result
