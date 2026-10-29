"""REST bridge exposing the Zero-Trust banking security layer to the frontend.

All endpoints live under ``/api/banking`` and require JWT auth + request signing.

Production zero-trust controls (defense in depth):

Layer 1 -- Frontend signs every banking request with Ed25519 (Web Crypto API).
   The backend verifies the signature and STID before processing.

Layer 2 -- Backend canonicalizes + schema-validates (Pydantic) before okgate.
   Rejects malformed/injected payloads (negative amounts, bad currencies, etc.)
   before they reach the policy gate.

Layer 3 -- okgate enforces business policy (tiers, MFA, confirmation, caps,
   approvals, loop breaker, kill switch, audit chain).

Layer 4 -- Backend re-signs the canonical payload for the bank/okgate upstream.
   Every forwarded call carries an Ed25519 signature proving backend intent.

Every security decision is written to a tamper-evident, hash-chained decision
log independent of okgate's audit.jsonl.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from cryptography.hazmat.primitives.serialization import load_pem_public_key
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

from app.dependencies import get_current_user, get_current_admin_user  # noqa: E402
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
from app.core.security.keys import load_private_key  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.schemas import (  # noqa: E402
    TransferPrepareRequest as SchemaTransferPrepare,
    TransferExecuteRequest as SchemaTransferExecute,
    TransferExecuteApproveRequest as SchemaTransferExecuteApprove,
    CallRequest as SchemaCallRequest,
    CreditorAccount,
)

router = APIRouter(prefix="/api/banking", tags=["banking-security"])
logger = logging.getLogger(__name__)
settings = get_settings()

#: Directory holding okgate.yaml and where okgate runs (cwd).
ROOT = BANKING_AGENT_DIR
#: okgate policy file (trust boundary -- never exposed for frontend writes).
POLICY = ROOT / "okgate.yaml"
#: Daily spend ledger (persisted on disk).
STATE_DIR = ROOT / ".state"
SPEND_LEDGER = STATE_DIR / "daily_spend.json"

#: Shared MFA verifier across requests.
MFA_CODE_STORE: dict[str, str] = {}

#: FX API configuration
FX_API_KEY: str = os.environ.get("EXCHANGERATE_API_KEY", "")
FX_API_BASE_URL: str = "https://v6.exchangerate-api.com/v6"
FX_CACHE_TTL_SECONDS: int = int(os.environ.get("FX_CACHE_TTL_SECONDS", "900"))

#: FX rate cache: {currency_pair: (rate, timestamp)}
FX_RATE_CACHE: dict[str, tuple[float, float]] = {}

#: FX conversion fee rate (percentage of converted amount)
FX_CONVERSION_FEE_RATE: float = 0.01  # 1% conversion fee
FX_RATES: dict[str, float] = {}


class FXRateRequest(BaseModel):
    from_currency: str = Field(..., min_length=3, max_length=3)
    to_currency: str = Field(..., min_length=3, max_length=3)
    rate: float = Field(..., gt=0)


class FXConversionRequest(BaseModel):
    from_currency: str = Field(..., min_length=3, max_length=3)
    to_currency: str = Field(..., min_length=3, max_length=3)
    amount: float = Field(..., gt=0)


def _normalize_currency(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise HTTPException(status_code=422, detail="Currency must be a 3-letter ISO code")
    return normalized


def _get_signing_key(request: Request):
    return getattr(request.app.state, "signing_private_key", None)


def _verify_frontend_signature(request: Request, body_bytes: bytes) -> dict[str, str]:
    """Verify the frontend's Ed25519 proof and bind it to this request."""
    signature = request.headers.get("X-Request-Signature")
    stid = request.headers.get("X-Request-STID")
    client_id = request.headers.get("X-Client-Id")
    timestamp = request.headers.get("X-Request-Timestamp")
    public_key_b64 = request.headers.get("X-Client-Public-Key")
    if not all((signature, stid, client_id, timestamp, public_key_b64)):
        raise HTTPException(status_code=401, detail="Banking request signature is required")

    try:
        if abs(time.time() - int(timestamp)) > 300:
            raise ValueError("stale request")
        public_key_pem = base64.b64decode(public_key_b64)
        public_key = load_pem_public_key(public_key_pem)
        body = json.loads(body_bytes.decode("utf-8")) if body_bytes else None
        canonical_body = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        expected_stid = compute_stid(
            request.method,
            request.url.path,
            canonical_body,
            client_id,
        )
        if expected_stid != stid or not verify_bytes(
            public_key, canonical_body.encode("utf-8"), signature
        ):
            raise ValueError("invalid signature")
    except (ValueError, TypeError, json.JSONDecodeError, base64.binascii.Error) as exc:
        raise HTTPException(status_code=401, detail="Invalid banking request signature") from exc

    return {"client_id": client_id, "stid": stid}


def transfer_outcome_to_dict(outcome: Any) -> dict[str, Any]:
    return {
        "ok": outcome.ok,
        "code": outcome.code,
        "message": outcome.message,
        "tier": outcome.tier.value if outcome.tier else None,
        "amount_cny": str(outcome.amount_cny) if outcome.amount_cny is not None else None,
        "projected_daily_cny": (
            str(outcome.projected_daily_cny)
            if outcome.projected_daily_cny is not None
            else None
        ),
        "intent_id": outcome.transfer_intent_id,
        "approval_id": outcome.approval_id,
        "approval_command": outcome.approval_command,
        "details": outcome.details or {},
        "value": outcome.value,
        "stage": getattr(outcome, "stage", None),
    }


async def _open_gate(user: models.User, request: Request):
    """Open the configured bank adapter; never use seeded data in production."""
    if settings.app_env.lower() in {"production", "staging"} and (
        os.environ.get("BANKING_BACKEND_MODE", "real").lower() == "mock"
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mock banking backend is disabled outside development",
        )
    client = GateClient(policy=POLICY, root=ROOT, run_id=f"banking-api-{user.user_id}")
    await client.open()
    try:
        gate = SecureBankGate(
            client=client,
            spend=DailySpendLedger(SPEND_LEDGER),
            mfa=SmsCodeMfa(deliver=lambda subject, challenge_id, code: MFA_CODE_STORE.__setitem__(challenge_id, code)),
            subject=str(user.user_id),
        )
        yield gate, client
    finally:
        await client.close()


def update_exchange_rate(from_currency: str, to_currency: str, rate: float) -> None:
    FX_RATES[f"{from_currency}{to_currency}"] = rate
    FX_RATE_CACHE[f"{from_currency}{to_currency}"] = (rate, time.time())


async def _fetch_exchange_rate(from_currency: str, to_currency: str) -> float | None:
    """Fetch exchange rate from exchangerate-api.com.

    Args:
        from_currency: Source currency code (e.g., "CNY")
        to_currency: Target currency code (e.g., "USD")

    Returns:
        Exchange rate (1 from_currency = rate to_currency) or None if unavailable
    """
    if not FX_API_KEY:
        return None

    url = f"{FX_API_BASE_URL}/{FX_API_KEY}/pair/{from_currency}/{to_currency}"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("result") == "success":
                    return float(data["conversion_rate"])
                else:
                    logger.warning(f"Exchange rate API error: {data.get('error-type', 'unknown')}")
            else:
                logger.warning(f"Exchange rate API returned status {resp.status_code}")
    except Exception as exc:
        logger.warning(f"Failed to fetch exchange rate: {exc}")

    return None


async def _get_exchange_rate(from_currency: str, to_currency: str) -> float:
    """Get exchange rate with caching.

    First tries real-time API, falls back to cached rates.

    Args:
        from_currency: Source currency code
        to_currency: Target currency code

    Returns:
        Exchange rate (1 from_currency = rate to_currency)
    """
    key = f"{from_currency}{to_currency}"

    if from_currency == to_currency:
        return 1.0

    # Check cache first (rate is valid for FX_CACHE_TTL_SECONDS)
    if key in FX_RATE_CACHE:
        rate, timestamp = FX_RATE_CACHE[key]
        if time.time() - timestamp < FX_CACHE_TTL_SECONDS:
            return rate

    # Try to fetch from API
    rate = await _fetch_exchange_rate(from_currency, to_currency)
    if rate is not None:
        FX_RATE_CACHE[key] = (rate, time.time())
        return rate

    rate = FX_RATES.get(key)
    if rate is not None:
        return rate

    # Try inverse rate
    inverse_key = f"{to_currency}{from_currency}"
    if inverse_key in FX_RATES:
        return round(1.0 / FX_RATES[inverse_key], 6)

    raise ValueError(f"No exchange rate available for {from_currency} to {to_currency}")


async def convert_currency_with_live_rate(
    amount: float, from_currency: str, to_currency: str
) -> dict[str, Any]:
    """Convert currency using real-time exchange rates from exchangerate-api.com.

    Args:
        amount: Amount in from_currency
        from_currency: Source currency code
        to_currency: Target currency code

    Returns:
        Conversion details dict
    """
    rate = await _get_exchange_rate(from_currency, to_currency)
    converted_amount = amount * rate
    fee = round(amount * FX_CONVERSION_FEE_RATE, 2)

    return {
        "original_amount": amount,
        "converted_amount": round(converted_amount, 2),
        "currency_from": from_currency,
        "currency_to": to_currency,
        "rate": rate,
        "fee": fee,
        "total_charged": round(amount + fee, 2),
    }


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@router.get("/tools")
async def list_tools(
    request: Request, user: models.User = Depends(get_current_user)
):
    """List tools the okgate proxy exposes (from client.tool_names())."""
    body_bytes = b""
    sig_info = _verify_frontend_signature(request, body_bytes)

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
    """Generic SecureBankGate.call -- any tool, any tier.

    Verifies frontend signature, validates schema, canonicalizes args,
    signs for okgate, and logs the decision.
    """
    public_key = _get_signing_key(request)
    body_bytes = await request.body()
    sig_info = _verify_frontend_signature(request, body_bytes)

    # Schema validation (Layer 1 defense-in-depth)
    try:
        SchemaCallRequest(
            tool=payload.tool,
            args=payload.args or None,
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
        finally:
            await client.close()

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

    result = transfer_outcome_to_dict(outcome)
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
    Layer 3: Idempotency key prevents double-execution on retries.
    """
    body_bytes = await request.body()
    sig_info = _verify_frontend_signature(request, body_bytes)

    # Check idempotency key - return cached response if duplicate request
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key:
        cached = _check_idempotency(idempotency_key)
        if cached is not None:
            return cached

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
            {"reason": f"schema_validation_failed: {ve.errors()}", "stid": sig_info["stid"]},
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
        finally:
            await client.close()

    # Backend re-signs the canonical payload for the bank/okgate upstream
    signing_key = _get_signing_key(request)
    backend_sig = None
    if signing_key is not None:
        backend_sig = sign_bytes(signing_key, canonical_args.encode("utf-8"))

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

    # Store idempotent response if key provided
    if idempotency_key:
        _store_idempotent_response(idempotency_key, result)

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

    # Check idempotency key - return cached response if duplicate request
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key:
        cached = _check_idempotency(idempotency_key)
        if cached is not None:
            return cached

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
        finally:
            await client.close()

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

    # Store idempotent response if key provided
    if idempotency_key:
        _store_idempotent_response(idempotency_key, result)

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
    """Return the delivered code for a challenge (SMS simulation only).

    In demo mode (DEMO_MODE=true), returns the code so the frontend can
    demonstrate the full MFA flow. In production, returns a message
    indicating the code was delivered via the real channel.
    """
    body_bytes = b""
    sig_info = _verify_frontend_signature(request, body_bytes)

    code = MFA_CODE_STORE.get(challenge_id)
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no code found for that challenge",
        )

    demo_mode = os.environ.get("DEMO_MODE", "false").lower() == "true"
    if demo_mode:
        return {"challenge_id": challenge_id, "code": code, "stid": sig_info["stid"]}
    else:
        return {
            "challenge_id": challenge_id,
            "message": "Code delivered to registered phone number",
            "stid": sig_info["stid"],
        }


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
    """Halt every call (kill switch). Requires admin role."""
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
    """Clear the kill switch and resume normal service. Requires admin role."""
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
async def status(
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
    """Verify the hash-chained integrity of both okgate audit and backend decision log."""
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


@router.post("/transfer/prepare")
async def transfer_prepare(
    request: Request,
    payload: TransferPrepareRequest,
    user: models.User = Depends(get_current_user),
):
    """Phase 1 of a transfer: price + reserve an intent (may need confirmation/MFA).

    Layer 1: Pydantic schema validation rejects invalid amounts/currencies.
    Layer 2: canonicalize + backend signing before okgate.
    Layer 3: Idempotency key prevents double-execution on retries.
    """
    body_bytes = await request.body()
    sig_info = _verify_frontend_signature(request, body_bytes)

    # Check idempotency key - return cached response if duplicate request
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key:
        cached = _check_idempotency(idempotency_key)
        if cached is not None:
            return cached

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
            {"reason": f"schema_validation_failed: {ve.errors()}", "stid": sig_info["stid"]},
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
        finally:
            await client.close()

    # Backend re-signs the canonical payload for the bank/okgate upstream
    signing_key = _get_signing_key(request)
    backend_sig = None
    if signing_key is not None:
        backend_sig = sign_bytes(signing_key, canonical_args.encode("utf-8"))

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

    # Store idempotent response if key provided
    if idempotency_key:
        _store_idempotent_response(idempotency_key, result)

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

    # Check idempotency key - return cached response if duplicate request
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key:
        cached = _check_idempotency(idempotency_key)
        if cached is not None:
            return cached

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
        finally:
            await client.close()

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

    # Store idempotent response if key provided
    if idempotency_key:
        _store_idempotent_response(idempotency_key, result)

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
    """Return the delivered code for a challenge (SMS simulation only).

    In demo mode (DEMO_MODE=true), returns the code so the frontend can
    demonstrate the full MFA flow. In production, returns a message
    indicating the code was delivered via the real channel.
    """
    body_bytes = b""
    sig_info = _verify_frontend_signature(request, body_bytes)

    code = MFA_CODE_STORE.get(challenge_id)
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no code found for that challenge",
        )

    demo_mode = os.environ.get("DEMO_MODE", "false").lower() == "true"
    if demo_mode:
        return {"challenge_id": challenge_id, "code": code, "stid": sig_info["stid"]}
    else:
        return {
            "challenge_id": challenge_id,
            "message": "Code delivered to registered phone number",
            "stid": sig_info["stid"],
        }


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
    """Halt every call (kill switch). Requires admin role."""
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
    """Clear the kill switch and resume normal service. Requires admin role."""
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
async def status(
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
    """Verify the hash-chained integrity of both okgate audit and backend decision log."""
    body_bytes = b""
    sig_info = _verify_frontend_signature(request, body_bytes)

    async for gate, client in _open_gate(user, request):
        try:
            result = await client.verify_audit()
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


@router.post("/transfer/prepare")
async def transfer_prepare(
    request: Request,
    payload: TransferPrepareRequest,
    user: models.User = Depends(get_current_user),
):
    """Phase 1 of a transfer: price + reserve an intent (may need confirmation/MFA).

    Layer 1: Pydantic schema validation rejects invalid amounts/currencies.
    Layer 2: canonicalize + backend signing before okgate.
    Layer 3: Idempotency key prevents double-execution on retries.
    """
    body_bytes = await request.body()
    sig_info = _verify_frontend_signature(request, body_bytes)

    # Check idempotency key - return cached response if duplicate request
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key:
        cached = _check_idempotency(idempotency_key)
        if cached is not None:
            return cached

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
            {"reason": f"schema_validation_failed: {ve.errors()}", "stid": sig_info["stid"]},
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
        finally:
            await client.close()

    # Backend re-signs the canonical payload for the bank/okgate upstream
    signing_key = _get_signing_key(request)
    backend_sig = None
    if signing_key is not None:
        backend_sig = sign_bytes(signing_key, canonical_args.encode("utf-8"))

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

    # Store idempotent response if key provided
    if idempotency_key:
        _store_idempotent_response(idempotency_key, result)

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
    result["stid"] = sig_info["stid"]
    result["backend_signature"] = backend_sig
    return result


@router.get("/tools")
async def list_tools(
    request: Request, user: models.User = Depends(get_current_user)
):
    """List tools the okgate proxy exposes (from client.tool_names())."""
    body_bytes = b""
    sig_info = _verify_frontend_signature(request, body_bytes)

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

# ============================================================================
# FX (Foreign Exchange) Rate Endpoints
# ============================================================================

@router.get("/fx/rates")
async def get_fx_rates(
    request: Request,
    from_currency: str = Query(..., min_length=3, max_length=3),
    to_currency: str = Query(..., min_length=3, max_length=3),
    user: models.User = Depends(get_current_user),
):
    """List all available exchange rates.

    Query parameters:
        from_currency: Source currency code (e.g., "CNY")
        to_currency: Target currency code (e.g., "USD")

    Returns:
        Exchange rate for the pair.
    """
    from_currency = _normalize_currency(from_currency)
    to_currency = _normalize_currency(to_currency)
    body_bytes = b""
    sig_info = _verify_frontend_signature(request, body_bytes)

    try:
        rate = await _get_exchange_rate(from_currency, to_currency)
        return {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "rate": rate,
            "challenge_id": sig_info["stid"],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post("/fx/rates")
async def set_fx_rate(
    request: Request,
    payload: FXRateRequest,
    user: models.User = Depends(get_current_admin_user),
):
    """Set or update an FX rate (admin only).

    Args:
        from_currency: Source currency code (e.g., "CNY")
        to_currency: Target currency code (e.g., "USD")
        rate: Exchange rate (1 from_currency = rate to_currency)
    """
    from_currency = _normalize_currency(payload.from_currency)
    to_currency = _normalize_currency(payload.to_currency)
    body_bytes = await request.body()
    sig_info = _verify_frontend_signature(request, body_bytes)

    _log_decision(
        user.user_id,
        "fx_rate_update",
        {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "rate": payload.rate,
            "client_id": sig_info["client_id"],
            "stid": sig_info["stid"],
        },
        "ok",
        {"new_rate": payload.rate},
    )

    update_exchange_rate(from_currency, to_currency, payload.rate)

    return {
        "message": f"FX rate updated: 1 {from_currency} = {payload.rate} {to_currency}",
        "from_currency": from_currency,
        "to_currency": to_currency,
        "rate": payload.rate,
        "stid": sig_info["stid"],
    }


@router.post("/fx/convert")
async def convert_currency_endpoint(
    request: Request,
    payload: FXConversionRequest,
    user: models.User = Depends(get_current_user),
):
    """Convert an amount from one currency to another using current FX rates.

    Args:
        from_currency: Source currency code (e.g., "CNY")
        to_currency: Target currency code (e.g., "USD")
        amount: Amount to convert in from_currency

    Returns:
        Conversion details including converted amount, rate, fee, total charged
    """
    from_currency = _normalize_currency(payload.from_currency)
    to_currency = _normalize_currency(payload.to_currency)
    body_bytes = await request.body()
    sig_info = _verify_frontend_signature(request, body_bytes)

    try:
        conversion = await convert_currency_with_live_rate(
            payload.amount, from_currency, to_currency
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    _log_decision(
        user.user_id,
        "fx_convert",
        {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "amount": payload.amount,
            "client_id": sig_info["client_id"],
            "stid": sig_info["stid"],
        },
        "ok",
        {
            "converted_amount": conversion["converted_amount"],
            "fee": conversion["fee"],
        },
    )

    return {
        "challenge_id": sig_info["stid"],
        "conversion": conversion,
    }
