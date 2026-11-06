"""Interpret a CFO chat turn before dispatching it to a bank operation."""

from __future__ import annotations

import logging
from typing import Any

from app.services.llm_banking_agent import LLMSelector
from app.services.llm_factory import get_llm_client
from app.services.mode_service import resolve_mode

logger = logging.getLogger(__name__)

_INTENTS = {"balance", "transaction_summary", "transfer", "conversation", "other"}
_DIRECTIONS = {"CREDIT", "DEBIT"}
_PERIODS = {"all_time", "last_month", "this_month", "this_year"}

_SYSTEM_PROMPT = """Interpret the user's banking/CFO message. Understand natural wording,
minor spelling mistakes, and English or Chinese. Do not execute actions or invent
account facts. Return only JSON with this shape:
{"intent":"balance|transaction_summary|transfer|conversation|other",
 "confidence":0.0,
 "direction":"CREDIT|DEBIT|null",
 "period":"all_time|last_month|this_month|this_year",
 "amount":null,
 "recipient_name":null,
 "currency":"CNY",
 "reply":null}
Use transaction_summary for questions about money received/income (CREDIT) or
money spent/paid/outgoing (DEBIT). Use transfer only when the user wants to move
money between people/accounts. Extract an amount and recipient only when stated.
If unclear whether the user requests a transfer or which person/amount, lower
confidence; do not guess. Greetings and ordinary conversation are conversation.
For conversation, write a brief, natural reply in the user's language. Do not claim
to know personal balances, transactions, or other private facts; those require a
FINN data lookup.
"""


def interpret_cfo_intent(message: str, mode: str | None = None) -> dict[str, Any] | None:
    """Return a validated intent; callers still enforce all banking permissions."""
    try:
        client = get_llm_client(resolve_mode(mode))
        raw = client.invoke_agent(
            prompt=f"USER MESSAGE:\n{message}",
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=300,
        )
    except Exception:
        logger.exception("CFO intent interpretation failed")
        return None

    if isinstance(raw, dict) and "error" in raw:
        logger.warning("CFO intent model returned an error: %s", raw["error"])
        return None
    if isinstance(raw, dict) and raw.get("intent") in _INTENTS:
        parsed = raw
    else:
        text = raw.get("response") if isinstance(raw, dict) else str(raw)
        parsed = LLMSelector._parse_json(text)
    if not isinstance(parsed, dict) or parsed.get("intent") not in _INTENTS:
        logger.warning("CFO intent interpreter returned an invalid response")
        return None

    try:
        confidence = float(parsed.get("confidence", 0))
    except (TypeError, ValueError):
        return None
    if not 0 <= confidence <= 1:
        return None

    intent = parsed["intent"]
    direction = parsed.get("direction")
    if direction not in _DIRECTIONS:
        direction = None
    period = parsed.get("period")
    if period not in _PERIODS:
        period = "all_time"
    amount = parsed.get("amount")
    recipient_name = parsed.get("recipient_name")
    if amount is not None and not isinstance(amount, (str, int, float)):
        amount = None
    if recipient_name is not None and not isinstance(recipient_name, str):
        recipient_name = None
    currency = parsed.get("currency")
    if not isinstance(currency, str):
        currency = "CNY"
    reply = parsed.get("reply")
    if not isinstance(reply, str):
        reply = None

    return {
        "intent": intent,
        "confidence": confidence,
        "direction": direction,
        "period": period,
        "amount": amount,
        "recipient_name": recipient_name.strip() if recipient_name else None,
        "currency": currency.upper(),
        "reply": reply.strip() if reply else None,
    }
