"""Shared banking service for Zero-Trust transfers.

This module contains the core business logic for banking operations that is
shared between:
1. The FastAPI REST API (`app/routers/banking.py`)
2. The WeCom IM integration (`app/integrations/wecom_bot.py`)

Both entry points use the SAME service functions, ensuring identical
Zero-Trust enforcement (tier classification, MFA, caps, approvals, kill switch,
audit logging) regardless of the channel used.

All functions return dicts with consistent shapes:
- {"ok": bool, "code": str, "message": str, "tier": str|None, ...}
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional, Tuple

from fastapi import Request

# Make `banking_agent` importable (it lives one level up from `app/`).
REPO_ROOT = Path(__file__).resolve().parents[2]
BANKING_AGENT_DIR = REPO_ROOT / "banking-agent"
if str(BANKING_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(BANKING_AGENT_DIR))

from banking_agent.gate import (  # noqa: E402
    DailySpendLedger,
    GateClient,
    GateCode,
    GateOutcome,
    SecureBankGate,
    SmsCodeMfa,
    Tier,
    TransferOutcome,
)

from app.core.security.signing import (  # noqa: E402
    compute_stid,
    canonicalize,
    hash_payload,
    sign_bytes,
    verify_bytes,
    generate_client_id,
)
from app.core.security.audit_ledger import (  # noqa: E402
    decision_ledger,
)
from app.core.security.keys import load_private_key  # noqa: E402
from app.schemas import (  # noqa: E402
    TransferPrepareRequest,
    TransferExecuteRequest,
    TransferExecuteApproveRequest,
    CallRequest,
    CreditorAccount,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Global (module-level) shared state
# --------------------------------------------------------------------------- #

_MFA_CODE_STORE: dict[str, str] = {}
_MFA_VERIFIER: Optional[SmsCodeMfa] = None
_DAILY_Spend_LEDGER: Optional[DailySpendLedger] = None
_SECURE_BANK_GATE: Optional[SecureBankGate] = None


def _get_mfa_verifier() -> SmsCodeMfa:
    """Get or create the shared MFA verifier."""
    global _MFA_VERIFIER
    if _MFA_VERIFIER is None:
        def _deliver(subject: str, challenge_id: str, code: str) -> None:
            _MFA_CODE_STORE[challenge_id] = code
        _MFA_VERIFIER = SmsCodeMfa(deliver=_deliver)
    return _MFA_VERIFIER


def _get_daily_spend_ledger() -> DailySpendLedger:
    """Get or create the shared daily spend ledger."""
    global _D_AILY_Spend_LEDGER
    if _D_AILY_Spend_LEDGER is None:
        from pathlib import Path as _Path
        ledger_path = BANKING_AGENT_DIR / ".state" / "daily_spend.json"
        _D_AILY_Spend_LEDGER = DailySpendLedger(ledger_path)
    return _D_AILY_Spend_LEDGER


# --------------------------------------------------------------------------- #
# Core service function
# --------------------------------------------------------------------------- #


async def process_banking_request(
    *,
    tool: str,
    args: dict[str, Any],
    confirmed: bool = False,
    mfa_challenge_id: Optional[str] = None,
    mfa_code: Optional[str] = None,
    subject: str = "account-holder",
    user_id: str = "web-user",
    signing_key: Any = None,
    decision_ledger: Any = None,
) -> dict[str, Any]:
    """Process a banking request through the full Zero-Trust pipeline.

    This is the CORE service function used by both the FastAPI router and
    the WeCom IM integration. It enforces:

    1. Schema validation (Pydantic)
    2. Canonicalization + hash for deterministic signing
    3. Tier classification (Green/Yellow/Red)
    4. okgate proxy execution (caps, approvals, kill switch, loop breaker)
    5. Backend re-signing for the bank upstream
    6. Tamper-evident audit logging

    Args:
        tool: The banking tool name (e.g., "get-accounts", "prepare-transfer")
        args: Tool arguments (e.g., {"amount": 600, "currency": "CNY"})
        confirmed: Whether the user has confirmed the transfer
        mfa_challenge_id: MFA challenge ID (for Red-tier verification)
        mfa_code: MFA code entered by user
        subject: Subject of the call (typically "account-holder")
        user_id: Internal user ID for audit logging
        signing_key: Ed25519 private key for backend re-signing
        decision_ledger: Audit ledger instance

    Returns:
        Dict with outcome details:
        - ok: bool - Whether the operation succeeded
        - code: str - Gate outcome code (OK, CONFIRMATION_REQUIRED, MFA_REQUIRED, etc.)
        - tier: str|None - Green/Yellow/Red
        - message: str - Human-readable message
        - intent_id: str|None - Transfer intent ID (for prepare/execute)
        - approval_id: str|None - Approval ID (if approval required)
        - needs_confirmation: bool
        - needs_mfa: bool
        - needs_approval: bool
        - backend_signature: str|None - Ed25519 signature
        - stage: str - Processing stage
        - error: str|None - Error message if failed
    """
    stage = "init"

    try:
        # ===================================================================
        # Layer 1: Schema Validation
        # ===================================================================
        # Validate the request against Pydantic models before anything else.
        # This rejects malformed/injected payloads early.

        tool_normalized = tool.lower()

        if tool_normalized == "get-accounts":
            SchemaCallRequest(tool=tool, args=args or {})
        elif tool_normalized == "prepare-transfer":
            SchemaTransferPrepare(
                debtor_account_id=args.get("debtor_account_id", ""),
                creditor=args.get("creditor", {}),
                amount=args.get("amount", 0),
                currency=args.get("currency", "CNY"),
                rail=args.get("rail", "swift"),
                description=args.get("description"),
            )
        elif tool_normalized == "execute-transfer":
            SchemaTransferExecute(intent_id=args.get("intent_id", ""))
        elif tool_normalized == "execute-transfer-approve":
            TransferExecuteApproveRequest(approval_id=args.get("approval_id", ""))
        else:
            # Generic call - validate minimally
            SchemaCallRequest(tool=tool, args=args or {})

        # ===================================================================
        # Layer 2: Canonicalization
        # ===================================================================
        # Canonicalize the args for deterministic signing.
        canonical_args = canonicalize(args or {})
        args_hash = hash_payload(canonical_args)

        # ===================================================================
        # Layer 3: okgate execution
        # ===================================================================
        # Build the SecureBankGate and execute the call through okgate.
        # okgate enforces: tiers, MFA, confirmation, caps, approvals,
        # loop breaker, kill switch, audit chain.

        client = GateClient(policy=POLICY, root=ROOT, run_id=f"banking-api-{user_id}")
        await client.open()

        try:
            gate = SecureBankGate(
                client=client,
                spend=_get_daily_spend_ledger(),
                mfa=_get_mfa_verifier(),
                subject=subject,
            )

            outcome = await gate.call(
                tool,
                args or None,
                confirmed=confirmed,
                mfa_challenge_id=mfa_challenge_id,
                mfa_code=mfa_code,
            )
        except Exception as exc:
            logger.error(f"okgate call failed: {exc}")
            _log_decision(
                user_id,
                "call",
                {"tool": tool, "args": args, "client_id": user_id},
                "error",
                {"error": str(exc)},
            )
            return {
                "ok": False,
                "code": "EXECUTE_ERROR",
                "message": str(exc),
                "tier": None,
                "stage": "error",
                "error": str(exc),
            }
        finally:
            await client.close()

        # ===================================================================
        # Layer 4: Backend re-signing
        # ===================================================================
        # Re-sign the canonical payload for the bank/okgate upstream.
        backend_sig = None
        if signing_key is not None:
            backend_sig = sign_bytes(signing_key, canonical_args.encode("utf-8"))

        # ===================================================================
        # Layer 5: Audit logging
        # ===================================================================
        _log_decision(
            user_id,
            "call",
            {
                "tool": tool,
                "args": args,
                "client_id": user_id,
                "args_hash": args_hash,
            },
            "ok" if outcome.ok else "refused",
            {
                "code": outcome.code,
                "tier": outcome.tier.value if outcome.tier else None,
                "backend_signature": backend_sig,
            },
        )

        return {
            "ok": outcome.ok,
            "code": outcome.code,
            "tier": outcome.tier.value if outcome.tier else None,
            "message": outcome.message,
            "amount_cny": _dec(outcome.amount_cny),
            "projected_daily_cny": _dec(outcome.projected_daily_cny),
            "intent_id": outcome.transfer_intent_id,
            "approval_id": outcome.approval_id,
            "approval_command": outcome.approval_command,
            "needs_confirmation": outcome.code == GateCode.CONFIRMATION_REQUIRED.value,
            "needs_mfa": outcome.code == GateCode.MFA_REQUIRED.value,
            "needs_approval": outcome.code == GateCode.APPROVAL_REQUIRED.value,
            "details": outcome.details or {},
            "value": outcome.value,
            "stage": stage,
            "backend_signature": backend_sig,
        }

    except Exception as exc:
        logger.exception(f"Unexpected error in process_banking_request: {exc}")
        _log_decision(
            user_id,
            "call",
            {"tool": tool, "args": args, "client_id": user_id},
            "error",
            {"error": str(exc)},
        )
        return {
            "ok": False,
            "code": "INTERNAL_ERROR",
            "message": str(exc),
            "tier": None,
            "stage": "error",
            "error": str(exc),
        }


async def _open_gate(user_id: str, subject: str = "account-holder"):
    """Open a fresh GateClient and build a SecureBankGate for one request."""
    client = GateClient(policy=POLICY, root=ROOT, run_id=f"banking-api-{user_id}")
    await client.open()
    try:
        gate = SecureBankGate(
            client=client,
            spend=_get_daily_spend_ledger(),
            mfa=_get_mfa_verifier(),
            subject=subject,
        )
        yield gate, client
    finally:
        await client.close()


def _log_decision(
    actor: str,
    action: str,
    payload: dict[str, Any],
    outcome: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write a security decision to the tamper-evident ledger."""
    if decision_ledger is not None:
        try:
            decision_ledger.append(actor, action, payload, outcome, metadata)
        except Exception:
            pass  # ledger failures must not block banking operations


# Module-level references for convenience
POLICY = BANKING_AGENT_DIR / "okgate.yaml"
ROOT = BANKING_AGENT_DIR
STATE_DIR = BANKING_AGENT_DIR / ".state"
SPEND_LEDGER = STATE_DIR / "daily_spend.json"

# Expose commonly used symbols
__all__ = [
    "process_banking_request",
    "_open_gate",
    "_log_decision",
    "POLICY",
    "ROOT",
    "STATE_DIR",
    "SPEND_LEDGER",
]
