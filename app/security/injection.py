"""Prompt injection scan (section 13.4)."""

from __future__ import annotations

import re
from typing import List, Tuple

INJECTION_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("ignore_previous_instructions", re.compile(r"ignore\s+previous\s+instructions", re.I)),
    (
        "disregard_instructions",
        re.compile(r"disregard\s+(prior|previous|above)\s+instructions", re.I),
    ),
    ("system_override", re.compile(r"system\s*:\s*you\s+are", re.I)),
    ("send_payment_now", re.compile(r"send\s+payment\s+now\s+to\s+account", re.I)),
    ("transfer_to_account", re.compile(r"transfer\s+\w+\s+to\s+account", re.I)),
    (
        "role_override",
        re.compile(
            r"you\s+are\s+now\s+(a\s+)?(different|new)\s+(ai|assistant|model|administrator)", re.I
        ),
    ),
    ("jailbreak", re.compile(r"jailbreak", re.I)),
    ("dan", re.compile(r"dan\s*(do\s+anything\s+now)?", re.I)),
    ("reveal_system_prompt", re.compile(r"reveal\s+your\s+(system\s+)?prompt", re.I)),
    ("base64_instruction", re.compile(r"base64", re.I)),
    ("zero_width", re.compile(r"[\u200b-\u200d\ufeff]")),
    ("data_url_leak", re.compile(r"data:.*base64", re.I)),
    ("markdown_link_leak", re.compile(r"\[[^\]]*\]\([^)]*(?:[?&].*=|%[0-9a-fA-F]{2})[^)]*\)")),
    ("autonomy_change", re.compile(r"change\s+(the\s+)?autonomy\s+level", re.I)),
]


def scan_injection(text: str) -> bool:
    """Return True if text looks like a prompt injection attempt."""
    if not text:
        return False
    for _name, pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def scan_chunks(chunks) -> tuple:
    """Scan a list of text chunks. Returns (clean_chunks, flagged_chunks)."""
    clean = []
    flagged = []
    for chunk in chunks:
        text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
        if scan_injection(text):
            flagged.append(chunk)
        else:
            clean.append(chunk)
    return clean, flagged
