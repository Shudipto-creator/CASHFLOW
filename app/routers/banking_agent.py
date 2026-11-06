"""REST bridge to the LLM banking agent (Scenario 1: Smart Transfer).

Lets a caller "send a message to the agent" over HTTP:

    POST /api/banking/agent/chat  {"message": "transfer ¥600 to 李娜"}

The agent maps the message onto a *registered, implemented* banking operation
(using RAG over the operations catalog to stay in context), hard-guards the
choice against the registry so the LLM can never invent an operation, and — for
implemented operations only — executes it through the Zero-Trust banking gate.

Authentication: JWT (``get_current_user``), matching the Ask-CFO chat rather
than the signed banking endpoints. The operations the agent runs are themselves
enforced by the banking gate (tiers / MFA / confirmation / okgate caps /
approvals / audit).
"""

from __future__ import annotations

import logging
import hashlib
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import yaml

from app import models
from app.database import get_db
from app.dependencies import get_current_user
from app.config import get_settings
from app.services.mode_service import resolve_mode
from app.services.llm_banking_agent import BankingExecutor, LLMBankingAgent, AgentResult, _transfer_args
from app.services import finn_bank
from app.services.cfo_intent import interpret_cfo_intent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/banking", tags=["banking-agent"])
settings = get_settings()

#: Repo root = banking-agent/ lives one level up from app/.
REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY = REPO_ROOT / "banking-agent" / "okgate.yaml"
GATE_ROOT = REPO_ROOT / "banking-agent"
STATE_DIR = GATE_ROOT / ".state"
VECTOR_STORE_DIR = REPO_ROOT / "data" / "vector_store"
if str(GATE_ROOT) not in sys.path:
    sys.path.insert(0, str(GATE_ROOT))
from banking_agent.gate import DailySpendLedger, SmsCodeMfa, YELLOW_DAILY_CEILING_CNY


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    recipient_customer_id: Optional[str] = None
    processing_mode: Optional[str] = None  # "aws" | "local" | None (global default)
    confirmed: bool = False                # answer a Yellow confirmation prompt
    confirmation_id: Optional[str] = None
    mfa_challenge_id: Optional[str] = None
    mfa_code: Optional[str] = None


class AgentTransferApprovalRequest(BaseModel):
    intent_id: str = Field(..., min_length=1)
    approval_id: str = Field(..., min_length=1)


class AgentChatResponse(BaseModel):
    implemented: bool
    code: str
    operation_id: Optional[str] = None
    message: str
    rationale: Optional[str] = None
    proposed_operation_id: Optional[str] = None
    retrieved_operations: list[str] = []
    execution: Optional[dict[str, Any]] = None
    processing_mode: Optional[str] = None


#: Process-lifetime agent cache: one agent per processing mode.
_AGENT_CACHE: dict[str, LLMBankingAgent] = {}
_PENDING_TRANSFER_APPROVALS: dict[tuple[str, str], tuple[str, str]] = {}
_PENDING_FINN_CONFIRMATIONS: dict[tuple[str, str], tuple[str, str, float, str, str, datetime]] = {}

_FINN_TRANSFER_MFA = SmsCodeMfa()
_FINN_TRANSFER_MFA_OWNERS: dict[str, tuple[str, datetime, str]] = {}


def _is_balance_question(message: str) -> bool:
    """Recognise safe account-balance questions without depending on an LLM."""
    text = message.casefold()
    return bool(re.search(
        r"\b(?:balance|balances|funds)\b"
        r"|\bhow much\b.{0,60}\b(?:account|money|funds|balance|have)\b"
        r"|\b(?:what(?:'s| is)|show|tell me)\b.{0,40}\b(?:my )?(?:account )?(?:balance|funds)\b"
        r"|余额|余额多少|有多少钱|账户金额",
        text,
    ))


def _balance_reply(user: models.User) -> str:
    """Build a factual reply only from the user's mapped FINN accounts."""
    accounts = finn_bank.accounts_for(user).get("items", [])
    if not accounts:
        return "You do not have any FINN accounts assigned yet."
    lines = []
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for account in accounts:
        try:
            balance = Decimal(str(account["availableBalance"]))
        except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
            logger.error("FINN account balance is missing or invalid for user %s", user.user_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="FINN account balance data is unavailable.",
            ) from exc
        if not balance.is_finite():
            logger.error("FINN account balance is not finite for user %s", user.user_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="FINN account balance data is unavailable.",
            )
        currency = str(account.get("currency") or "CNY").upper()
        totals[currency] += balance
        lines.append(
            f"{account.get('name', 'Account')} ending {str(account.get('accountNumber', ''))[-4:]}: "
            f"{currency} {balance:,.2f} available"
        )
    total_lines = [
        f"Total available in {currency}: {amount:,.2f}."
        for currency, amount in sorted(totals.items())
    ]
    return "Your available balances:\n" + "\n".join(lines) + "\n\n" + "\n".join(total_lines)


def _transaction_summary_request(message: str) -> tuple[str, str | None, str | None] | None:
    text = message.casefold()
    asks_income = bool(re.search(
        r"\b(?:income|earnings?|money\s+(?:i\s+)?received|amount\s+received)\b|收入|进账",
        text,
    ))
    asks_spending = bool(re.search(
        r"\b(?:spending|spend|expenses?|money\s+(?:i\s+)?spent|outgoings?)\b|支出|花费",
        text,
    ))
    if asks_income == asks_spending:
        return None

    today = datetime.now().date()
    start_date = end_date = None
    if re.search(r"\b(?:last|previous)\s+month\b|上个月|上月", text):
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
        start_date, end_date = start.isoformat(), end.isoformat()
    elif re.search(r"\bthis\s+month\b|本月|这个月", text):
        start_date, end_date = today.replace(day=1).isoformat(), today.isoformat()
    elif re.search(r"\bthis\s+year\b|今年", text):
        start_date, end_date = today.replace(month=1, day=1).isoformat(), today.isoformat()

    return ("CREDIT" if asks_income else "DEBIT", start_date, end_date)


def _transaction_summary_reply(
    user: models.User,
    direction: str,
    start_date: str | None,
    end_date: str | None,
) -> str:
    summary = finn_bank.transaction_totals_for(user, direction, start_date, end_date)
    items = summary.get("items", [])
    period = "all available history"
    if start_date and end_date:
        period = f"{start_date} to {end_date}"

    if not items:
        label = "income (money in)" if direction == "CREDIT" else "spending (money out)"
        return f"No recorded {label} was found for {period}."

    lines = []
    for item in items:
        try:
            total = Decimal(str(item["total"]))
            count = int(item["transaction_count"])
            currency = str(item["currency"]).upper()
        except (KeyError, InvalidOperation, TypeError, ValueError):
            logger.error("FINN transaction summary is invalid for user %s", user.user_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="FINN transaction summary data is unavailable.",
            )
        if not total.is_finite() or count < 0:
            logger.error("FINN transaction summary is invalid for user %s", user.user_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="FINN transaction summary data is unavailable.",
            )
        amount = f"¥{total:,.2f}" if currency == "CNY" else f"{currency} {total:,.2f}"
        lines.append(f"{amount} across {count} transaction(s)")

    label = "recorded income (money in)" if direction == "CREDIT" else "recorded spending (money out)"
    reply = f"Your {label} for {period}: " + "; ".join(lines) + "."
    if direction == "CREDIT":
        reply += " This includes incoming transfers, which are not necessarily earned income."
    else:
        reply += " This includes transfers you sent as well as other outgoing transactions."
    return reply


def _transaction_dates_for_period(period: str) -> tuple[str | None, str | None]:
    today = datetime.now().date()
    if period == "last_month":
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1).isoformat(), end.isoformat()
    if period == "this_month":
        return today.replace(day=1).isoformat(), today.isoformat()
    if period == "this_year":
        return today.replace(month=1, day=1).isoformat(), today.isoformat()
    return None, None


def _is_transfer_request(message: str) -> bool:
    return bool(re.search(
        r"\btransfers?\b|\btransferts?\b|\bsend\s+(?:money|[¥￥]?\s*\d)|\bpay\s+[¥￥]?\s*\d|转账|汇款",
        message,
        re.IGNORECASE,
    ))


def _transfer_response(message: str, *, code: str, execution: dict[str, Any] | None = None) -> AgentChatResponse:
    return AgentChatResponse(
        implemented=True,
        code=code,
        operation_id="prepare-transfer",
        message=message,
        rationale="FINNDB contact-based sandbox transfer",
        retrieved_operations=["prepare-transfer"],
        execution=execution,
        processing_mode="finn-direct",
    )


def _resolve_saved_contact(
    db: Session,
    user: models.User,
    name: str,
    customer_id: str | None = None,
) -> tuple[dict | None, bool]:
    contact_name = name.strip().removeprefix("@").strip()
    contacts = db.query(models.FinnContact).filter(
        models.FinnContact.user_id == user.user_id
    ).all()
    if customer_id is not None:
        selected = next((contact for contact in contacts if contact.customer_id == customer_id), None)
        if selected is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="That recipient is not in your saved contacts.",
            )
        target = finn_bank.transfer_customer(selected.customer_id)
        if target["name"].strip().casefold() != contact_name.casefold():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The selected recipient does not match the name in your message.",
            )
        return target, False

    exact_matches = []
    for contact in contacts:
        target = finn_bank.transfer_customer(contact.customer_id)
        if target["name"].strip().casefold() == contact_name.casefold():
            exact_matches.append(target)
    return (exact_matches[0], False) if len(exact_matches) == 1 else (None, len(exact_matches) > 1)


def _finn_daily_spend(user: models.User) -> DailySpendLedger:
    return DailySpendLedger(STATE_DIR / _user_scope(user) / "daily_spend.json")


def _finn_daily_hard_cap() -> Decimal:
    try:
        policy = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
        cap = Decimal(str(policy["caps"]["per_day"]["spend_usd"]))
    except (OSError, KeyError, TypeError, InvalidOperation, yaml.YAMLError) as exc:
        logger.exception("Could not read the transfer hard cap from %s", POLICY)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FINN transfer policy is unavailable.",
        ) from exc
    if not cap.is_finite() or cap <= 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FINN transfer policy has an invalid daily cap.",
        )
    return cap


async def _handle_finn_transfer(
    payload: AgentChatRequest,
    user: models.User,
    db: Session,
    interpreted_intent: dict[str, Any] | None = None,
) -> AgentChatResponse:
    parsed = _transfer_args(payload.message)
    if interpreted_intent:
        if interpreted_intent.get("amount") is not None:
            parsed["amount"] = interpreted_intent["amount"]
        if interpreted_intent.get("recipient_name"):
            parsed["creditor_name"] = interpreted_intent["recipient_name"]
        parsed["currency"] = interpreted_intent.get("currency", "CNY")
    currency = str(parsed.get("currency") or "CNY").upper()
    if currency != "CNY" or re.search(r"\$|€|\b(?:usd|eur|dollars?)\b", payload.message, re.IGNORECASE):
        return _transfer_response(
            "FINNDB demo transfers currently support CNY only. Enter the amount in CNY.",
            code="UNSUPPORTED_CURRENCY",
        )
    recipient_name = str(parsed.get("creditor_name") or "").strip().strip("\"'“”‘’")
    if not recipient_name:
        return _transfer_response(
            "Tell me the saved contact's name and the amount to transfer, for example: “Transfer ¥50 to @Alex.”",
            code="RECIPIENT_REQUIRED",
        )
    if not parsed.get("amount"):
        return _transfer_response(
            f"How much would you like to transfer to {recipient_name}?",
            code="AMOUNT_REQUIRED",
        )
    try:
        amount = Decimal(str(parsed["amount"]))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Enter a valid transfer amount.") from exc
    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
        raise HTTPException(status_code=422, detail="Transfer amount must be positive and have at most two decimal places.")

    recipient, ambiguous_recipient = _resolve_saved_contact(
        db,
        user,
        recipient_name,
        payload.recipient_customer_id,
    )
    if ambiguous_recipient:
        return _transfer_response(
            f"More than one saved contact matches @{recipient_name.lstrip('@')}. "
            "Please specify the recipient's full name so I can identify the right person.",
            code="RECIPIENT_AMBIGUOUS",
        )
    if recipient is None:
        return _transfer_response(
            f"@{recipient_name.lstrip('@')} is not in your saved contacts. Add them in Contacts before sending money.",
            code="RECIPIENT_NOT_SAVED",
        )
    source = finn_bank.transfer_account_for(user)
    destination = finn_bank.transfer_account_for_customer(recipient["customer_id"])
    amount_value = float(amount)
    daily_spend = _finn_daily_spend(user)
    hard_cap = _finn_daily_hard_cap()
    projected_daily_spend = daily_spend.spent_today() + amount
    if amount > hard_cap or projected_daily_spend > hard_cap:
        return _transfer_response(
            f"This transfer exceeds the FINN daily limit of CNY {hard_cap:,.0f}.",
            code="DAILY_LIMIT_EXCEEDED",
        )
    needs_mfa = projected_daily_spend > YELLOW_DAILY_CEILING_CNY
    preview = {
        "source_account_id": source["id"],
        "source_account_name": source["name"],
        "recipient_name": recipient["name"],
        "amount": amount_value,
        "currency": "CNY",
    }

    pending_key = (str(user.user_id), payload.confirmation_id or "")
    if not payload.confirmed:
        confirmation_id = uuid4().hex
        now = datetime.now(timezone.utc)
        for key, value in list(_PENDING_FINN_CONFIRMATIONS.items()):
            if value[-1] <= now:
                _PENDING_FINN_CONFIRMATIONS.pop(key, None)
        for challenge_key, challenge_owner in list(_FINN_TRANSFER_MFA_OWNERS.items()):
            if challenge_owner[1] <= now:
                _FINN_TRANSFER_MFA_OWNERS.pop(challenge_key, None)
        challenge_id = None
        if needs_mfa:
            challenge_id = await _FINN_TRANSFER_MFA.challenge(
                subject=str(user.user_id),
                purpose=f"FINNDB transfer to {recipient['name']}",
            )
            _FINN_TRANSFER_MFA_OWNERS[challenge_id] = (
                str(user.user_id),
                now + timedelta(minutes=2),
                confirmation_id,
            )
        _PENDING_FINN_CONFIRMATIONS[(str(user.user_id), confirmation_id)] = (
            recipient["customer_id"],
            source["id"],
            amount_value,
            destination["account_number"],
            recipient["name"],
            now + timedelta(minutes=5),
        )
        return _transfer_response(
            "Review the transfer details and confirm to continue.",
            code="CONFIRMATION_REQUIRED",
            execution={
                "ok": False,
                "code": "CONFIRMATION_REQUIRED",
                "needs_confirmation": True,
                "needs_mfa": needs_mfa,
                "mfa_challenge_id": challenge_id,
                "confirmation_id": confirmation_id,
                "transfer_preview": preview,
            },
        )

    pending = _PENDING_FINN_CONFIRMATIONS.get(pending_key)
    if pending is None or pending[-1] <= datetime.now(timezone.utc):
        _PENDING_FINN_CONFIRMATIONS.pop(pending_key, None)
        return _transfer_response(
            "This transfer confirmation expired. Start the transfer again.",
            code="CONFIRMATION_EXPIRED",
        )
    if pending[:5] != (
        recipient["customer_id"],
        source["id"],
        amount_value,
        destination["account_number"],
        recipient["name"],
    ):
        return _transfer_response(
            "The transfer details changed. Start the transfer again to review the updated details.",
            code="TRANSFER_DETAILS_CHANGED",
        )
    projected_daily_spend = daily_spend.spent_today() + amount
    if amount > hard_cap or projected_daily_spend > hard_cap:
        _PENDING_FINN_CONFIRMATIONS.pop(pending_key, None)
        return _transfer_response(
            f"This transfer exceeds the FINN daily limit of CNY {hard_cap:,.0f}.",
            code="DAILY_LIMIT_EXCEEDED",
        )
    if projected_daily_spend > YELLOW_DAILY_CEILING_CNY:
        challenge_id = payload.mfa_challenge_id or ""
        challenge_owner = _FINN_TRANSFER_MFA_OWNERS.get(challenge_id)
        if challenge_owner is None and not challenge_id:
            challenge_id = await _FINN_TRANSFER_MFA.challenge(
                subject=str(user.user_id),
                purpose=f"FINNDB transfer to {recipient['name']}",
            )
            _FINN_TRANSFER_MFA_OWNERS[challenge_id] = (
                str(user.user_id),
                datetime.now(timezone.utc) + timedelta(minutes=2),
                payload.confirmation_id or "",
            )
            return _transfer_response(
                "The daily total now requires additional verification. Enter the new code and confirm again.",
                code="MFA_REQUIRED",
                execution={
                    "ok": False,
                    "code": "MFA_REQUIRED",
                    "needs_confirmation": True,
                    "needs_mfa": True,
                    "mfa_challenge_id": challenge_id,
                    "confirmation_id": payload.confirmation_id,
                    "transfer_preview": preview,
                },
            )
        if (
            challenge_owner is None
            or challenge_owner[0] != str(user.user_id)
            or challenge_owner[1] <= datetime.now(timezone.utc)
            or challenge_owner[2] != payload.confirmation_id
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MFA verification failed.")
        if not await _FINN_TRANSFER_MFA.verify(challenge_id=challenge_id, code=payload.mfa_code or ""):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MFA verification failed.")
        _FINN_TRANSFER_MFA_OWNERS.pop(challenge_id, None)

    _PENDING_FINN_CONFIRMATIONS.pop(pending_key, None)
    intent_id = finn_bank.prepare_transfer(
        user,
        debtor_account_id=source["id"],
        creditor_name=recipient["name"],
        creditor_account_number=destination["account_number"],
        amount=amount_value,
        currency="CNY",
        description=f"FINN transfer to {recipient['name']}",
        creditor_customer_id=destination["customer_id"],
        require_internal=True,
    )
    daily_spend.add(amount)
    approval_id = f"finn_approval_{uuid4().hex}"
    _PENDING_TRANSFER_APPROVALS[(str(user.user_id), intent_id)] = (approval_id, "finn")
    return _transfer_response(
        "Transfer prepared. Approve to send the money.",
        code="APPROVAL_REQUIRED",
        execution={
            "ok": False,
            "code": "APPROVAL_REQUIRED",
            "needs_approval": True,
            "intent_id": intent_id,
            "approval_id": approval_id,
            "transfer_preview": preview,
        },
    )


def _user_scope(user: models.User) -> str:
    """Use an opaque, filesystem-safe scope for per-user gate state."""
    return hashlib.sha256(str(user.user_id).encode("utf-8")).hexdigest()[:20]


def _get_agent(mode: str, user: models.User) -> LLMBankingAgent:
    scope = _user_scope(user)
    cache_key = f"{scope}:{mode}"
    agent = _AGENT_CACHE.get(cache_key)
    if agent is None:
        user_state = STATE_DIR / scope
        agent = LLMBankingAgent.build(
            policy=POLICY,
            root=GATE_ROOT,
            state_dir=user_state,
            persist_dir=VECTOR_STORE_DIR,
            subject=str(user.user_id),
            run_id=f"llm-agent-{scope}-{mode}",
            use_llm=True,
        )
        _AGENT_CACHE[cache_key] = agent
        logger.info("Built LLM banking agent (mode=%s)", mode)
    return agent


@router.get("/demo-data")
async def demo_bank_data(
    count: int = Query(10, ge=1, le=500),
    user: models.User = Depends(get_current_user),
):
    """Return only the authenticated user's FINN customer data."""
    return {
        "source": "finn",
        "accounts": finn_bank.accounts_for(user),
        "transactions": finn_bank.transactions_for(user, count),
    }


@router.post("/agent/chat", response_model=AgentChatResponse)
async def agent_chat(
    payload: AgentChatRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a message to the LLM banking agent and get its action back."""
    # Balance data is factual, customer-scoped banking information. Resolve it
    # directly from FINN rather than asking an LLM to infer or fabricate it.
    if _is_balance_question(payload.message):
        return AgentChatResponse(
            implemented=True,
            code="OK",
            operation_id="get-accounts",
            message=_balance_reply(user),
            rationale="Customer-scoped FINN account balance lookup",
            retrieved_operations=["get-accounts"],
            execution={"source": "finn", "customer_scoped": True},
            processing_mode="finn-direct",
        )
    transaction_summary = _transaction_summary_request(payload.message)
    if transaction_summary:
        direction, start_date, end_date = transaction_summary
        return AgentChatResponse(
            implemented=True,
            code="OK",
            operation_id="get-transactions-summary",
            message=_transaction_summary_reply(user, direction, start_date, end_date),
            rationale="Customer-scoped FINN transaction summary",
            retrieved_operations=["get-transactions-summary"],
            execution={
                "source": "finn",
                "customer_scoped": True,
                "direction": direction,
                "start_date": start_date,
                "end_date": end_date,
            },
            processing_mode="finn-direct",
        )
    transfer_request = _is_transfer_request(payload.message)
    parsed_transfer = _transfer_args(payload.message) if transfer_request else {}
    if parsed_transfer.get("amount") and parsed_transfer.get("creditor_name"):
        return await _handle_finn_transfer(payload, user, db)
    interpreted_intent = interpret_cfo_intent(payload.message, payload.processing_mode)
    if interpreted_intent and interpreted_intent["intent"] == "transfer":
        if interpreted_intent["confidence"] >= 0.6:
            return await _handle_finn_transfer(payload, user, db, interpreted_intent)
        return _transfer_response(
            "I may have misunderstood. If you want to make a transfer, please tell me the exact contact and amount.",
            code="TRANSFER_CLARIFICATION_REQUIRED",
        )
    if interpreted_intent and interpreted_intent["confidence"] >= 0.6:
        if interpreted_intent["intent"] == "balance":
            return AgentChatResponse(
                implemented=True,
                code="OK",
                operation_id="get-accounts",
                message=_balance_reply(user),
                rationale="AI-interpreted customer-scoped FINN account balance lookup",
                retrieved_operations=["get-accounts"],
                execution={"source": "finn", "customer_scoped": True},
                processing_mode="finn-direct",
            )
        if interpreted_intent["intent"] == "transaction_summary" and interpreted_intent["direction"]:
            direction = interpreted_intent["direction"]
            start_date, end_date = _transaction_dates_for_period(interpreted_intent["period"])
            return AgentChatResponse(
                implemented=True,
                code="OK",
                operation_id="get-transactions-summary",
                message=_transaction_summary_reply(user, direction, start_date, end_date),
                rationale="AI-interpreted customer-scoped FINN transaction summary",
                retrieved_operations=["get-transactions-summary"],
                execution={
                    "source": "finn",
                    "customer_scoped": True,
                    "direction": direction,
                    "start_date": start_date,
                    "end_date": end_date,
                },
                processing_mode="finn-direct",
            )
        if interpreted_intent["intent"] == "transaction_summary":
            return AgentChatResponse(
                implemented=True,
                code="CLARIFICATION_REQUIRED",
                operation_id="get-transactions-summary",
                message="Are you asking about money coming into your accounts or money going out?",
                rationale="AI-interpreted transaction summary needs a direction",
                retrieved_operations=["get-transactions-summary"],
                execution={"source": "finn", "customer_scoped": True},
                processing_mode="finn-direct",
            )
        if interpreted_intent["intent"] == "conversation":
            return AgentChatResponse(
                implemented=True,
                code="OK",
                message=interpreted_intent.get("reply") or "I'm here to help. What would you like to know about your money?",
                rationale="Natural-language CFO conversation",
                processing_mode="cfo-conversation",
            )
        if interpreted_intent["intent"] == "other":
            return AgentChatResponse(
                implemented=True,
                code="OK",
                message=interpreted_intent.get("reply") or "I can help with your accounts, money in or out, and transfers. What would you like to check?",
                rationale="Natural-language CFO conversation",
                processing_mode="cfo-conversation",
            )
    if transfer_request:
        return await _handle_finn_transfer(payload, user, db)
    mode = resolve_mode(payload.processing_mode)
    agent = _get_agent(mode, user)

    result: AgentResult = await agent.handle(
        payload.message,
        confirmed=payload.confirmed,
        mfa_challenge_id=payload.mfa_challenge_id,
        mfa_code=payload.mfa_code,
        excluded_operations={"prepare-transfer"},
    )

    if (
        result.operation_id == "prepare-transfer"
        and result.execution
        and result.execution.get("needs_approval")
        and result.execution.get("intent_id")
        and result.execution.get("approval_id")
    ):
        _PENDING_TRANSFER_APPROVALS[
            (str(user.user_id), result.execution["intent_id"])
        ] = (result.execution["approval_id"], mode)

    return AgentChatResponse(
        implemented=result.implemented,
        code=result.code,
        operation_id=result.operation_id,
        message=result.message,
        rationale=result.selected.rationale,
        proposed_operation_id=result.selected.proposed_operation_id,
        retrieved_operations=result.retrieved,
        execution=result.execution,
        processing_mode=mode,
    )


@router.post("/agent/transfer/approve")
async def agent_transfer_approve(
    payload: AgentTransferApprovalRequest,
    user: models.User = Depends(get_current_user),
):
    """Release the human approval for a prepared sandbox transfer."""
    key = (str(user.user_id), payload.intent_id)
    pending = _PENDING_TRANSFER_APPROVALS.get(key)
    if pending is None or pending[0] != payload.approval_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That transfer approval was not found for your signed-in account.",
        )

    _, mode = pending
    if mode == "finn":
        try:
            result = finn_bank.execute_transfer(user, payload.intent_id)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Could not execute FINNDB transfer for user %s", user.user_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The FINNDB transfer could not be completed.",
            ) from exc
        if result.get("transfer_id"):
            _PENDING_TRANSFER_APPROVALS.pop(key, None)
            result.update({"ok": True, "message": "Transfer completed successfully."})
        return result

    agent = _get_agent(mode, user)
    if not agent.executor:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Transfer service unavailable.")
    try:
        result = await agent.executor.approve_transfer(payload.intent_id, payload.approval_id)
    except Exception as exc:
        logger.exception("Could not approve sandbox transfer for user %s", user.user_id)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="The transfer could not be completed.") from exc

    if result.get("ok"):
        _PENDING_TRANSFER_APPROVALS.pop(key, None)
    return result
