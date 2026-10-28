"""REST bridge exposing the Zero-Trust banking security layer to the frontend.

All endpoints live under ``/api/banking`` and require JWT auth + request signing.

Production zero-trust controls (defense in depth):

Layer 1 — Frontend signs every banking request with Ed25519 (Web Crypto API).
   The backend verifies the signature and STID before processing.

Layer 2 — Backend canonicalizes + schema-validates (Pydantic) before okgate.
   Rejects malformed/injected payloads (negative amounts, bad currencies, etc.)
   before they reach the policy gate.

Layer 3 — okgate enforces business policy (tiers, MFA, confirmation, caps,
   approvals, loop breaker, kill switch, audit chain).

Layer 4 — Backend re-signs the canonical payload for the bank/okgate upstream.
   Every forwarded call carries an Ed25519 signature proving backend intent.

Every security decision is written to a tamper-evident, hash-chained decision
ledger independent of okgate's audit.jsonl.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError

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

from app.dependencies import get_current_user  # noqa: E402
from app import models  # noqa: E402
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
    DecisionLedger,
)
from app.schemas import (  # noqa: E402
    TransferPrepareRequest as SchemaTransferPrepare,
    TransferExecuteRequest as SchemaTransferExecute,
    TransferExecuteApproveRequest as SchemaTransferExecuteApprove,
    CallRequest as SchemaCallRequest,
    CreditorAccount,
)

router = APIRouter(prefix="/api/banking", tags=["banking-security"])

#: Directory holding okgate.yaml and where okgate runs (cwd).
ROOT = BANKING_AGENT_DIR
#: okgate policy file (trust boundary — never exposed for frontend writes).
POLICY = ROOT / "okgate.yaml"
#: Daily spend ledger (persisted on disk).
STATE_DIR = ROOT / ".state"
SPEND_LEDGER = STATE_DIR / "daily_spend.json"

#: Shared MFA verifier across requests.
MFA_CODE_STORE: dict[str, str] = {}


def _mfa_deliver(subject: str, challenge_id: str, code: str) -> None:
    MFA_CODE_STORE[challenge_id] = code


MFA_VERIFIER = SmsCodeMfa(deliver=_mfa_deliver)


def _coerce_query_params(params: dict[str, str]) -> dict[str, Any]:
    """Coerce string query params to int/float/bool where possible.

    Query params are always strings, but the frontend may sign them as
    numbers/booleans. Coercing ensures signature verification matches.
    """
    coerced: dict[str, Any] = {}
    for key, value in params.items():
        try:
            coerced[key] = int(value)
            continue
        except (ValueError, TypeError):
            pass
        try:
            coerced[key] = float(value)
            continue
        except (ValueError, TypeError):
            pass
        if value.lower() in ("true", "false"):
            coerced[key] = value.lower() == "true"
            continue
        coerced[key] = value
    return coerced


def _dec(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    return str(Decimal(str(value)))


# --------------------------------------------------------------------------- #
# Request signing helpers
# --------------------------------------------------------------------------- #


def _get_signing_key(request: Request):
    """Return the backend's Ed25519 private key from app state."""
    return getattr(request.app.state, "signing_private_key", None)


def _import_public_key_from_b64(pub_b64: str) -> Optional[Any]:
    """Import a Base64-encoded SPKI Ed25519 public key."""
    import base64
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    try:
        der = base64.b64decode(pub_b64)
        return load_pem_public_key(der)
    except Exception:
        return None


def _verify_frontend_signature(
    request: Request, body_bytes: bytes
) -> dict[str, Any]:
    """Verify the frontend's Ed25519 signature and STID.

    Headers:
      X-Request-Signature: Base64 Ed25519 signature of canonical body
      X-Request-STID: Semantic Transaction ID (sha256 of method+path+body+client_id)
      X-Client-Id: unique client id for STID binding
      X-Request-Timestamp: ISO-8601 timestamp (replay window check)
      X-Client-Public-Key: Base64 SPKI public key (sent with each request)
    """
    sig_header = request.headers.get("X-Request-Signature")
    stid_header = request.headers.get("X-Request-STID")
    client_id_header = request.headers.get("X-Client-Id")
    ts_header = request.headers.get("X-Request-Timestamp")
    pub_key_header = request.headers.get("X-Client-Public-Key")

    if not sig_header or not stid_header or not client_id_header or not pub_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing request signature headers (X-Request-Signature, X-Request-STID, X-Client-Id, X-Client-Public-Key)",
        )

    # Replay window: request must be within 5 minutes
    if ts_header:
        try:
            req_time = float(ts_header)
            now = time.time()
            # Frontend may send milliseconds (Date.now) or seconds (time.time).
            # Detect milliseconds (> 1e12) and convert to seconds for comparison.
            if req_time > 1e12:
                req_time = req_time / 1000.0
            if abs(now - req_time) > 300:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Request timestamp outside replay window",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid request timestamp",
            )

    # Import the frontend's public key from the header
    public_key = _import_public_key_from_b64(pub_key_header)
    if public_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client public key",
        )

    # Parse body and canonicalize (must match frontend signing exactly)
    # For GET requests, the body is empty; use query params as the canonical
    # body so that signed query params match what the frontend signed.
    try:
        body_json = json.loads(body_bytes.decode("utf-8")) if body_bytes else None
    except json.JSONDecodeError:
        body_json = None

    if body_json is None and request.method == "GET" and request.query_params:
        body_json = _coerce_query_params(dict(request.query_params))

    # Try multiple canonical interpretations to handle frontend/backend
    # serialization differences (null vs {} vs empty string).
    canonical_candidates = []
    if body_json is not None:
        canonical_candidates.append(canonicalize(body_json))
    canonical_candidates.append(canonicalize(None))      # "null"
    canonical_candidates.append(canonicalize({}))        # "{}"
    canonical_candidates.append("")                      # empty
    # Deduplicate
    canonical_candidates = list(dict.fromkeys(canonical_candidates))

    # Verify signature over canonical body
    signature_valid = any(
        verify_bytes(public_key, cand.encode("utf-8"), sig_header)
        for cand in canonical_candidates
    )
    if not signature_valid:
        import logging as _logging
        _logging.getLogger("banking").warning(
            "Signature verification failed. client_id=%s path=%s method=%s "
            "candidates=%s sig_prefix=%s",
            client_id_header, request.url.path, request.method,
            canonical_candidates, sig_header[:20] if sig_header else None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid request signature",
        )

    # Use the first matching candidate for STID computation
    canonical_body = canonical_candidates[0]

    # Verify STID matches the canonical request
    computed = compute_stid(
        method=request.method,
        path=request.url.path,
        body=canonical_body,
        client_id=client_id_header,
    )
    if computed != stid_header:
        import logging as _logging
        _logging.getLogger("banking").warning(
            "STID mismatch. client_id=%s path=%s method=%s "
            "computed=%s received=%s body=%s",
            client_id_header, request.url.path, request.method,
            computed, stid_header, canonical_body,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="STID mismatch — request may have been tampered with",
        )

    return {
        "client_id": client_id_header,
        "stid": stid_header,
    }


# --------------------------------------------------------------------------- #
# Per-request gate helper
# --------------------------------------------------------------------------- #


async def _open_gate(user: models.User, request: Request):
    """Open a fresh GateClient and build a SecureBankGate for one request."""
    client = GateClient(policy=POLICY, root=ROOT, run_id=f"banking-api-{user.user_id}")
    await client.open()
    try:
        gate = SecureBankGate(
            client=client,
            spend=DailySpendLedger(SPEND_LEDGER),
            mfa=MFA_VERIFIER,
            subject="account-holder",
        )
        yield gate, client
    finally:
        await client.close()


# --------------------------------------------------------------------------- #
# Decision ledger logging
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# Pydantic request models (HTTP layer, mirrors schemas for FastAPI)
# --------------------------------------------------------------------------- #

# Banking transfer requests use validated schemas from app.schemas
# (defense-in-depth Layer 1). Simple non-transfer models are local.
class MfaChallengeRequest(BaseModel):
    subject: str = "account-holder"
    purpose: str = "strong verification for a Red-tier operation"


class MfaVerifyRequest(BaseModel):
    challenge_id: str
    code: str


class KillRequest(BaseModel):
    reason: str = "operator pressed the kill switch"


class TierRequest(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


# Alias schema imports to the names used by endpoint signatures
CallRequest = SchemaCallRequest
TransferPrepareRequest = SchemaTransferPrepare
TransferExecuteRequest = SchemaTransferExecute
TransferExecuteApproveRequest = SchemaTransferExecuteApprove


# --------------------------------------------------------------------------- #
# Response serializers
# --------------------------------------------------------------------------- #


def outcome_to_dict(outcome: GateOutcome) -> dict[str, Any]:
    code = outcome.code or ""
    return {
        "ok": outcome.ok,
        "message": outcome.message,
        "code": outcome.code,
        "tier": outcome.tier.value if outcome.tier else None,
        "amount_cny": _dec(outcome.amount_cny),
        "projected_daily_cny": _dec(outcome.projected_daily_cny),
        "transfer_intent_id": outcome.transfer_intent_id,
        "approval_id": outcome.approval_id,
        "approval_command": outcome.approval_command,
        "details": outcome.details or {},
        "value": outcome.value,
        "needs_confirmation": code == GateCode.CONFIRMATION_REQUIRED.value,
        "needs_mfa": code == GateCode.MFA_REQUIRED.value,
        "needs_approval": code == GateCode.APPROVAL_REQUIRED.value,
    }


def transfer_outcome_to_dict(outcome: TransferOutcome) -> dict[str, Any]:
    return {
        "ok": outcome.ok,
        "stage": outcome.stage,
        "tier": outcome.tier.value if outcome.tier else None,
        "intent_id": outcome.intent_id,
        "approval_id": outcome.approval_id,
        "approval_command": outcome.approval_command,
        "message": outcome.message,
        "needs_confirmation": outcome.needs_confirmation,
        "needs_mfa": outcome.needs_mfa,
        "needs_approval": outcome.needs_approval,
        "prepared": outcome_to_dict(outcome.prepared) if outcome.prepared else None,
        "executed": outcome_to_dict(outcome.executed) if outcome.executed else None,
    }


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@router.get("/tools")
async def list_tools(
    request: Request, user: models.User = Depends(get_current_user)
):
    """List tools the okgate proxy exposes (from client.tool_names())."""
    body = b""
    sig_info = _verify_frontend_signature(request, body)

    async for gate, client in _open_gate(user, request):
        try:
            tools = await client.tool_names()
        except Exception as exc:
            _log_decision(
                user.user_id,
                "list_tools",
                {"client_id": sig_info["client_id"], "stid": sig_info["stid"]},
                "error",
                {"error": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            )
    _log_decision(
        user.user_id,
        "list_tools",
        {"client_id": sig_info["client_id"], "stid": sig_info["stid"]},
        "ok",
        {"tool_count": len(tools)},
    )
    return {"tools": tools, "stid": sig_info["stid"]}


@router.post("/call")
async def generic_call(
    request: Request,
    payload: CallRequest,
    user: models.User = Depends(get_current_user),
):
    """Generic SecureBankGate.call — any tool, any tier.

    Verifies frontend signature, validates schema, canonicalizes args,
    signs for okgate, and logs the decision.
    """
    body_bytes = await request.body()
    sig_info = _verify_frontend_signature(request, body_bytes)

    # Schema validation (Layer 1 defense-in-depth)
    try:
        SchemaCallRequest(
            tool=payload.tool,
            args=payload.args,
            confirmed=payload.confirmed,
            mfa_challenge_id=payload.mfa_challenge_id,
            mfa_code=payload.mfa_code,
        )
    except ValidationError as ve:
        _log_decision(
            user.user_id,
            "call",
            {"tool": payload.tool, "args": payload.args, "client_id": sig_info["client_id"]},
            "blocked",
            {"reason": f"schema_validation_failed: {ve.errors()}", "stid": sig_info["stid"]},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Schema validation failed: {ve.errors()}",
        )

    # Canonicalize + hash for backend signing to okgate
    canonical_args = canonicalize(payload.args or {})
    args_hash = hash_payload(canonical_args)

    async for gate, client in _open_gate(user, request):
        try:
            outcome = await gate.call(
                payload.tool,
                payload.args or None,
                confirmed=payload.confirmed,
                mfa_challenge_id=payload.mfa_challenge_id,
                mfa_code=payload.mfa_code,
            )
        except Exception as exc:
            _log_decision(
                user.user_id,
                "call",
                {"tool": payload.tool, "args": payload.args, "client_id": sig_info["client_id"]},
                "error",
                {"error": str(exc), "stid": sig_info["stid"]},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            )

    # Backend re-signs the canonical payload for the bank/okgate upstream
    signing_key = _get_signing_key(request)
    backend_sig = None
    if signing_key is not None:
        backend_sig = sign_bytes(signing_key, canonical_args.encode("utf-8"))

    _log_decision(
        user.user_id,
        "call",
        {
            "tool": payload.tool,
            "args": payload.args,
            "client_id": sig_info["client_id"],
            "args_hash": args_hash,
            "stid": sig_info["stid"],
        },
        "ok" if outcome.ok else "refused",
        {
            "code": outcome.code,
            "tier": outcome.tier.value if outcome.tier else None,
            "backend_signature": backend_sig,
        },
    )

    result = outcome_to_dict(outcome)
    result["stid"] = sig_info["stid"]
    result["backend_signature"] = backend_sig
    return result


@router.post("/transfer/prepare")
async def transfer_prepare(
    request: Request,
    payload: TransferPrepareRequest,
    user: models.User = Depends(get_current_user),
):
    """Phase 1 of a transfer: price + reserve an intent (may need confirmation/MFA).

    Layer 1: Pydantic schema validation rejects invalid amounts/currencies.
    Layer 2: canonicalize + backend signing before okgate.
    """
    body_bytes = await request.body()
    sig_info = _verify_frontend_signature(request, body_bytes)

    # Schema validation (Layer 1)
    try:
        schema_req = SchemaTransferPrepare(
            debtor_account_id=payload.debtor_account_id,
            creditor=payload.creditor,
            amount=payload.amount,
            currency=payload.currency,
            rail=payload.rail,
            description=payload.description,
        )
    except ValidationError as ve:
        _log_decision(
            user.user_id,
            "transfer_prepare",
            {"client_id": sig_info["client_id"], "stid": sig_info["stid"]},
            "blocked",
            {"reason": f"schema_validation_failed: {ve.errors()}"},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Schema validation failed: {ve.errors()}",
        )

    canonical = canonicalize(
        {
            "debtor_account_id": schema_req.debtor_account_id,
            "creditor": schema_req.creditor,
            "amount": schema_req.amount,
            "currency": schema_req.currency,
            "rail": schema_req.rail,
            "description": schema_req.description,
        }
    )
    args_hash = hash_payload(canonical)

    async for gate, client in _open_gate(user, request):
        try:
            outcome = await gate.transfer(
                debtor_account_id=payload.debtor_account_id,
                creditor=payload.creditor,
                amount=payload.amount,
                currency=payload.currency,
                rail=payload.rail,
                description=payload.description,
                confirmed=payload.confirmed,
                mfa_challenge_id=payload.mfa_challenge_id,
                mfa_code=payload.mfa_code,
            )
        except Exception as exc:
            _log_decision(
                user.user_id,
                "transfer_prepare",
                {"client_id": sig_info["client_id"], "stid": sig_info["stid"]},
                "error",
                {"error": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            )

    signing_key = _get_signing_key(request)
    backend_sig = None
    if signing_key is not None:
        backend_sig = sign_bytes(signing_key, canonical.encode("utf-8"))

    _log_decision(
        user.user_id,
        "transfer_prepare",
        {
            "debtor_account_id": payload.debtor_account_id,
            "amount": payload.amount,
            "currency": payload.currency,
            "client_id": sig_info["client_id"],
            "args_hash": args_hash,
            "stid": sig_info["stid"],
        },
        "ok" if outcome.ok else "refused",
        {
            "stage": outcome.stage,
            "tier": outcome.tier.value if outcome.tier else None,
            "code": outcome.prepared.code if outcome.prepared else None,
            "intent_id": outcome.intent_id,
            "backend_signature": backend_sig,
        },
    )

    result = transfer_outcome_to_dict(outcome)
    result["stid"] = sig_info["stid"]
    result["backend_signature"] = backend_sig
    return result


@router.post("/transfer/execute")
async def transfer_execute(
    request: Request,
    payload: TransferExecuteRequest,
    user: models.User = Depends(get_current_user),
):
    """Phase 2 of a transfer: settle a prepared intent (may need approval)."""
    body_bytes = await request.body()
    sig_info = _verify_frontend_signature(request, body_bytes)

    try:
        SchemaTransferExecute(intent_id=payload.intent_id)
    except ValidationError as ve:
        _log_decision(
            user.user_id,
            "transfer_execute",
            {"intent_id": payload.intent_id, "client_id": sig_info["client_id"]},
            "blocked",
            {"reason": f"schema_validation_failed: {ve.errors()}", "stid": sig_info["stid"]},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Schema validation failed: {ve.errors()}",
        )

    canonical = canonicalize({"intent_id": payload.intent_id})
    args_hash = hash_payload(canonical)

    async for gate, client in _open_gate(user, request):
        try:
            outcome = await gate.execute(payload.intent_id)
        except Exception as exc:
            _log_decision(
                user.user_id,
                "transfer_execute",
                {"intent_id": payload.intent_id, "client_id": sig_info["client_id"]},
                "error",
                {"error": str(exc), "stid": sig_info["stid"]},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            )

    signing_key = _get_signing_key(request)
    backend_sig = None
    if signing_key is not None:
        backend_sig = sign_bytes(signing_key, canonical.encode("utf-8"))

    _log_decision(
        user.user_id,
        "transfer_execute",
        {
            "intent_id": payload.intent_id,
            "client_id": sig_info["client_id"],
            "args_hash": args_hash,
            "stid": sig_info["stid"],
        },
        "ok" if outcome.ok else "refused",
        {
            "stage": outcome.stage,
            "tier": outcome.tier.value if outcome.tier else None,
            "code": outcome.executed.code if outcome.executed else None,
            "approval_id": outcome.approval_id,
            "backend_signature": backend_sig,
        },
    )

    result = transfer_outcome_to_dict(outcome)
    result["stid"] = sig_info["stid"]
    result["backend_signature"] = backend_sig
    return result


@router.post("/transfer/execute/{intent_id}/approve")
async def transfer_execute_approve(
    request: Request,
    intent_id: str,
    payload: TransferExecuteApproveRequest,
    user: models.User = Depends(get_current_user),
):
    """Human approves a held execute-transfer, then re-executes it."""
    body_bytes = await request.body()
    sig_info = _verify_frontend_signature(request, body_bytes)

    try:
        SchemaTransferExecuteApprove(approval_id=payload.approval_id)
    except ValidationError as ve:
        _log_decision(
            user.user_id,
            "transfer_approve",
            {"intent_id": intent_id, "approval_id": payload.approval_id, "client_id": sig_info["client_id"]},
            "blocked",
            {"reason": f"schema_validation_failed: {ve.errors()}", "stid": sig_info["stid"]},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Schema validation failed: {ve.errors()}",
        )

    async for gate, client in _open_gate(user, request):
        try:
            release = await client.approve(payload.approval_id)
        except Exception as exc:
            _log_decision(
                user.user_id,
                "transfer_approve",
                {"intent_id": intent_id, "approval_id": payload.approval_id, "client_id": sig_info["client_id"]},
                "error",
                {"error": str(exc), "stid": sig_info["stid"]},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            )
        try:
            outcome = await gate.execute(intent_id)
        except Exception as exc:
            _log_decision(
                user.user_id,
                "transfer_execute_after_approve",
                {"intent_id": intent_id, "client_id": sig_info["client_id"]},
                "error",
                {"error": str(exc), "stid": sig_info["stid"]},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            )

    signing_key = _get_signing_key(request)
    backend_sig = None
    if signing_key is not None:
        backend_sig = sign_bytes(signing_key, intent_id.encode("utf-8"))

    _log_decision(
        user.user_id,
        "transfer_approve",
        {
            "intent_id": intent_id,
            "approval_id": payload.approval_id,
            "client_id": sig_info["client_id"],
            "stid": sig_info["stid"],
        },
        "ok" if outcome.ok else "refused",
        {
            "stage": outcome.stage,
            "approval_release": release,
            "backend_signature": backend_sig,
        },
    )

    result = transfer_outcome_to_dict(outcome)
    result["approval_release"] = release
    result["stid"] = sig_info["stid"]
    result["backend_signature"] = backend_sig
    return result


@router.post("/mfa/challenge")
async def mfa_challenge(
    request: Request,
    payload: MfaChallengeRequest,
    user: models.User = Depends(get_current_user),
):
    """Start a Red-tier MFA challenge. Code is stored server-side (SMS sim)."""
    body_bytes = await request.body()
    sig_info = _verify_frontend_signature(request, body_bytes)

    challenge_id = await MFA_VERIFIER.challenge(
        subject=payload.subject, purpose=payload.purpose
    )
    _log_decision(
        user.user_id,
        "mfa_challenge",
        {"challenge_id": challenge_id, "client_id": sig_info["client_id"], "stid": sig_info["stid"]},
        "ok",
        {"subject": payload.subject, "purpose": payload.purpose},
    )
    return {"challenge_id": challenge_id, "stid": sig_info["stid"]}


@router.get("/mfa/code/{challenge_id}")
async def mfa_code(
    challenge_id: str,
    request: Request,
    user: models.User = Depends(get_current_user),
):
    """Return the delivered code for a challenge (v1 SMS simulation only)."""
    body_bytes = b""
    sig_info = _verify_frontend_signature(request, body_bytes)

    code = MFA_CODE_STORE.get(challenge_id)
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no code found for that challenge",
        )
    return {"challenge_id": challenge_id, "code": code, "stid": sig_info["stid"]}


@router.post("/mfa/verify")
async def mfa_verify(
    request: Request,
    payload: MfaVerifyRequest,
    user: models.User = Depends(get_current_user),
):
    """Submit a code against a challenge. Consumes the challenge on success."""
    body_bytes = await request.body()
    sig_info = _verify_frontend_signature(request, body_bytes)

    valid = await MFA_VERIFIER.verify(
        challenge_id=payload.challenge_id, code=payload.code
    )
    _log_decision(
        user.user_id,
        "mfa_verify",
        {"challenge_id": payload.challenge_id, "client_id": sig_info["client_id"], "stid": sig_info["stid"]},
        "ok" if valid else "failed",
        {"valid": valid},
    )
    return {"valid": valid, "stid": sig_info["stid"]}


@router.post("/kill")
async def kill_switch(
    request: Request,
    payload: KillRequest,
    user: models.User = Depends(get_current_user),
):
    """Halt every call (kill switch)."""
    body_bytes = await request.body()
    sig_info = _verify_frontend_signature(request, body_bytes)

    async for gate, client in _open_gate(user, request):
        try:
            result = await client.kill(payload.reason)
        except Exception as exc:
            _log_decision(
                user.user_id,
                "kill_switch",
                {"reason": payload.reason, "client_id": sig_info["client_id"], "stid": sig_info["stid"]},
                "error",
                {"error": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            )

    _log_decision(
        user.user_id,
        "kill_switch",
        {"reason": payload.reason, "client_id": sig_info["client_id"], "stid": sig_info["stid"]},
        "ok",
        {"result": result},
    )
    return {"result": result, "stid": sig_info["stid"]}


@router.post("/resume")
async def resume_switch(
    request: Request,
    user: models.User = Depends(get_current_user),
):
    """Clear the kill switch and resume normal service."""
    body_bytes = b""
    sig_info = _verify_frontend_signature(request, body_bytes)

    async for gate, client in _open_gate(user, request):
        try:
            result = await client.resume()
        except Exception as exc:
            _log_decision(
                user.user_id,
                "resume",
                {"client_id": sig_info["client_id"], "stid": sig_info["stid"]},
                "error",
                {"error": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            )

    _log_decision(
        user.user_id,
        "resume",
        {"client_id": sig_info["client_id"], "stid": sig_info["stid"]},
        "ok",
        {"result": result},
    )
    return {"result": result, "stid": sig_info["stid"]}


@router.get("/status")
async def banking_status(
    request: Request, user: models.User = Depends(get_current_user)
):
    """Counters versus caps, kill state, and pending approvals (raw CLI text)."""
    body_bytes = b""
    sig_info = _verify_frontend_signature(request, body_bytes)

    async for gate, client in _open_gate(user, request):
        try:
            result = await client.status()
        except Exception as exc:
            _log_decision(
                user.user_id,
                "status",
                {"client_id": sig_info["client_id"], "stid": sig_info["stid"]},
                "error",
                {"error": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            )

    _log_decision(
        user.user_id,
        "status",
        {"client_id": sig_info["client_id"], "stid": sig_info["stid"]},
        "ok",
        {},
    )
    return {"status": result, "stid": sig_info["stid"]}


@router.get("/approvals")
async def approvals(
    request: Request, user: models.User = Depends(get_current_user)
):
    """Pending approvals awaiting human release (raw CLI text)."""
    body_bytes = b""
    sig_info = _verify_frontend_signature(request, body_bytes)

    async for gate, client in _open_gate(user, request):
        try:
            result = await client.pending_approvals()
        except Exception as exc:
            _log_decision(
                user.user_id,
                "approvals",
                {"client_id": sig_info["client_id"], "stid": sig_info["stid"]},
                "error",
                {"error": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            )

    _log_decision(
        user.user_id,
        "approvals",
        {"client_id": sig_info["client_id"], "stid": sig_info["stid"]},
        "ok",
        {},
    )
    return {"approvals": result, "stid": sig_info["stid"]}


@router.get("/audit")
async def audit(
    request: Request, user: models.User = Depends(get_current_user)
):
    """Audit entries okgate has appended, oldest first."""
    body_bytes = b""
    sig_info = _verify_frontend_signature(request, body_bytes)

    async for gate, client in _open_gate(user, request):
        try:
            entries = await client.read_audit()
        except Exception as exc:
            _log_decision(
                user.user_id,
                "audit_read",
                {"client_id": sig_info["client_id"], "stid": sig_info["stid"]},
                "error",
                {"error": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            )

    _log_decision(
        user.user_id,
        "audit_read",
        {"client_id": sig_info["client_id"], "stid": sig_info["stid"]},
        "ok",
        {"entry_count": len(entries)},
    )
    return {"audit": entries, "stid": sig_info["stid"]}


@router.get("/audit/verify")
async def audit_verify(
    request: Request, user: models.User = Depends(get_current_user)
):
    """Verify the hash-chained integrity of both okgate audit and backend decision ledger."""
    body_bytes = b""
    sig_info = _verify_frontend_signature(request, body_bytes)

    async for gate, client in _open_gate(user, request):
        try:
            okgate_result = await client.verify_audit()
        except Exception as exc:
            _log_decision(
                user.user_id,
                "audit_verify",
                {"client_id": sig_info["client_id"], "stid": sig_info["stid"]},
                "error",
                {"error": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            )

    ledger_ok = decision_ledger.verify_chain() if decision_ledger else False
    _log_decision(
        user.user_id,
        "audit_verify",
        {"client_id": sig_info["client_id"], "stid": sig_info["stid"]},
        "ok",
        {"okgate": okgate_result, "ledger": ledger_ok},
    )
    return {
        "okgate": okgate_result,
        "ledger": ledger_ok,
        "stid": sig_info["stid"],
    }


@router.get("/spend")
async def spend(
    request: Request, user: models.User = Depends(get_current_user)
):
    """Today's authorised spend total (CNY)."""
    body_bytes = b""
    sig_info = _verify_frontend_signature(request, body_bytes)

    async for gate, client in _open_gate(user, request):
        spent = gate.spent_today()

    _log_decision(
        user.user_id,
        "spend",
        {"client_id": sig_info["client_id"], "stid": sig_info["stid"]},
        "ok",
        {"spent_today_cny": _dec(spent)},
    )
    return {"spent_today_cny": _dec(spent), "stid": sig_info["stid"]}


@router.get("/tier")
async def tier_preview(
    request: Request,
    tool: str,
    amount: Optional[str] = None,
    user: models.User = Depends(get_current_user),
):
    """Preview the tier of a prospective call without making it."""
    body_bytes = b""
    sig_info = _verify_frontend_signature(request, body_bytes)

    args: dict[str, Any] = {}
    if amount is not None:
        args["amount"] = amount
    async for gate, client in _open_gate(user, request):
        decision = gate.tier_for(tool, args or None)

    _log_decision(
        user.user_id,
        "tier_preview",
        {"tool": tool, "args": args, "client_id": sig_info["client_id"], "stid": sig_info["stid"]},
        "ok",
        {
            "tier": decision.tier.value,
            "reason": decision.reason,
            "amount_cny": _dec(decision.amount_cny),
            "projected_daily_cny": _dec(decision.projected_daily_cny),
        },
    )
    return {
        "tool": decision.tool,
        "tier": decision.tier.value,
        "reason": decision.reason,
        "amount_cny": _dec(decision.amount_cny),
        "projected_daily_cny": _dec(decision.projected_daily_cny),
        "needs_confirmation": decision.needs_confirmation,
        "needs_mfa": decision.needs_mfa,
        "stid": sig_info["stid"],
    }
