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
from app.services.cfo_conversation import (
    append_message,
    delete_conversation,
    detect_language,
    is_follow_up,
    last_message_metadata,
    last_topic,
    latest_conversation_id,
    load_conversation,
    load_history,
    new_conversation_id,
    normalize_conversation_id,
    period_from_message,
)

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
    conversation_id: Optional[str] = Field(None, max_length=64)
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
    conversation_id: Optional[str] = None
    language: Optional[str] = None


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


def _balance_reply(user: models.User, language: str = "en") -> str:
    """Build a factual reply only from the user's mapped FINN accounts."""
    accounts = finn_bank.accounts_for(user).get("items", [])
    if not accounts:
        return (
            "你还没有分配 FINN 账户。"
            if language == "zh"
            else "You do not have any FINN accounts assigned yet."
        )
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
        last_four = str(account.get("accountNumber", ""))[-4:]
        if language == "zh":
            lines.append(
                f"{account.get('name', '账户')}（尾号 {last_four}）："
                f"{currency} {balance:,.2f} 可用"
            )
        else:
            lines.append(
                f"{account.get('name', 'Account')} ending {last_four}: "
                f"{currency} {balance:,.2f} available"
            )
    if language == "zh":
        total_lines = [
            f"{currency} 可用总额：{amount:,.2f}。"
            for currency, amount in sorted(totals.items())
        ]
        return "您的可用余额：\n" + "\n".join(lines) + "\n\n" + "\n".join(total_lines)
    total_lines = [
        f"Total available in {currency}: {amount:,.2f}."
        for currency, amount in sorted(totals.items())
    ]
    return "Your available balances:\n" + "\n".join(lines) + "\n\n" + "\n".join(total_lines)


def _transaction_summary_request(
    message: str,
    history: list[dict[str, Any]] | None = None,
) -> tuple[str, str | None, str | None] | None:
    """Recognise income/spending questions, including short follow-ups.

    "and last month?" has no direction of its own.  When the previous assistant
    turn was a transaction summary, it inherits that direction and only the
    period changes.
    """
    text = message.casefold()
    asks_income = bool(re.search(
        r"\b(?:income|earnings?|money\s+(?:i\s+)?received|amount\s+received)\b|收入|进账|入账|收到",
        text,
    ))
    asks_spending = bool(re.search(
        r"\b(?:spending|spend|expenses?|money\s+(?:i\s+)?spent|outgoings?)\b|支出|花费|花了|消费|开销|付了",
        text,
    ))
    if asks_income == asks_spending:
        if history and is_follow_up(message) and last_topic(history) == "transaction_summary":
            direction = str(last_message_metadata(history).get("direction") or "")
            if direction in {"CREDIT", "DEBIT"}:
                return (
                    direction,
                    *_transaction_dates_for_period(period_from_message(message) or "all_time"),
                )
        return None

    return (
        "CREDIT" if asks_income else "DEBIT",
        *_transaction_dates_for_period(period_from_message(message) or "all_time"),
    )


def _transaction_summary_reply(
    user: models.User,
    direction: str,
    start_date: str | None,
    end_date: str | None,
    language: str = "en",
) -> str:
    summary = finn_bank.transaction_totals_for(user, direction, start_date, end_date)
    items = summary.get("items", [])
    chinese = language == "zh"
    if start_date and end_date:
        period = f"{start_date} 至 {end_date}" if chinese else f"{start_date} to {end_date}"
    else:
        period = "全部可用历史" if chinese else "all available history"

    if not items:
        if chinese:
            label = "收入（转入）" if direction == "CREDIT" else "支出（转出）"
            return f"在{period}没有找到记录的{label}。"
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
        if chinese:
            lines.append(f"{amount}，共 {count} 笔交易")
        else:
            lines.append(f"{amount} across {count} transaction(s)")

    if chinese:
        label = "已入账收入（转入）" if direction == "CREDIT" else "已记录支出（转出）"
        reply = f"你在{period}的{label}：" + "；".join(lines) + "。"
        if direction == "CREDIT":
            reply += "其中包含转入款项，不一定是经营收入。"
        else:
            reply += "其中包含你主动转出的款项以及其他支出。"
        return reply

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


def _localize(language: str, english: str, chinese: str) -> str:
    return chinese if language == "zh" else english


_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def _reply_in_language(reply: str | None, language: str, fallback: str) -> str:
    """Keep a small local model from answering in the wrong language."""
    if not reply or not reply.strip():
        return fallback
    cjk = len(_CJK_PATTERN.findall(reply))
    if language == "zh":
        matches = cjk > 0
    else:
        # Allow a stray Chinese name inside an otherwise English answer.
        matches = cjk < max(3, len(reply) * 0.1)
    return reply if matches else fallback


_GREETING_MESSAGES = {
    "hi", "hello", "hey", "hithere", "hellothere", "goodmorning",
    "goodafternoon", "goodevening", "greetings", "你好", "您好", "嗨",
    "早上好", "下午好", "晚上好", "在吗",
}


def _greeting_reply(message: str, language: str) -> str | None:
    """Answer a greeting deterministically, in the user's language."""
    normalized = re.sub(r"[.!?,，。！？\s]+", "", (message or "").lower())
    if normalized not in _GREETING_MESSAGES:
        return None
    if language == "zh":
        return (
            "你好！我是 FINN，你的财务助手。我可以查询你的账户余额、收入与支出，"
            "也可以帮你向已保存的联系人转账。需要我做什么？"
        )
    return (
        "Hi! I'm FINN, your financial navigator. I can look up your balances, "
        "money in and out, and help you transfer to a saved contact. What would "
        "you like to do?"
    )


def _out_of_scope_reply(language: str) -> str:
    """Capability statement for questions FINN has no data for."""
    return _localize(
        language,
        "I can help with your FINN accounts, balances, money in and out, and "
        "transfers to saved contacts. I don't have information about that topic, "
        "so I won't guess. Ask me about your account and I'll look it up.",
        "我可以帮你查询 FINN 账户余额、收入与支出，以及向已保存联系人转账。"
        "这个话题我无法回答，也不会猜测。你可以问我账户相关的问题，我会为你查询。",
    )


def _topic_for_response(response: AgentChatResponse) -> str | None:
    """Normalise a reply into the topic remembered for follow-up turns."""
    if response.operation_id == "get-accounts":
        return "balance"
    if response.operation_id == "get-transactions-summary":
        return "transaction_summary"
    if response.operation_id == "prepare-transfer":
        return "transfer"
    if response.code == "GREETING":
        return "greeting"
    if response.processing_mode == "cfo-conversation":
        return "conversation"
    if response.code == "OUT_OF_SCOPE":
        return "out_of_scope"
    return None


def _conversation_metadata(response: AgentChatResponse) -> dict[str, Any]:
    """Store the state a later follow-up may need (direction, period, amount)."""
    execution = response.execution or {}
    metadata: dict[str, Any] = {
        "code": response.code,
        "operation_id": response.operation_id,
        "processing_mode": response.processing_mode,
    }
    for key in (
        "direction",
        "start_date",
        "end_date",
        "needs_confirmation",
        "needs_mfa",
        "needs_approval",
    ):
        if key in execution:
            metadata[key] = execution[key]
    preview = execution.get("transfer_preview")
    if isinstance(preview, dict):
        if preview.get("amount") is not None:
            metadata["amount"] = preview["amount"]
        if preview.get("recipient_name"):
            metadata["recipient_name"] = preview["recipient_name"]
    return metadata


def _transfer_context(
    message: str,
    parsed: dict[str, Any],
    history: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Carry recipient/amount from earlier turns for a short follow-up."""
    if not history or not is_follow_up(message):
        return None
    context: dict[str, Any] = {}
    if not parsed.get("creditor_name"):
        for item in reversed(history):
            if item.get("role") != "user":
                continue
            content = str(item.get("content") or "")
            match = re.search(r"@([^\s,，。!?！？]+)", content)
            if match is None:
                match = re.search(
                    r"\b(?:to|给)\s+([A-Za-z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff .'\-]{0,40})",
                    content,
                )
            if match:
                context["recipient_name"] = match.group(1).strip()
                break
    if not parsed.get("amount"):
        metadata = last_message_metadata(history, intent="transfer")
        if metadata.get("amount"):
            context["amount"] = metadata["amount"]
        else:
            for item in reversed(history):
                if item.get("role") != "user":
                    continue
                previous = _transfer_args(str(item.get("content") or ""))
                if previous.get("amount"):
                    context["amount"] = previous["amount"]
                    break
    if not context:
        return None
    context["currency"] = "CNY"
    return context


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
    language = detect_language(payload.message)
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
            _localize(
                language,
                "FINNDB demo transfers currently support CNY only. Enter the amount in CNY.",
                "FINNDB 演示转账目前仅支持人民币（CNY）。请输入人民币金额。",
            ),
            code="UNSUPPORTED_CURRENCY",
        )
    recipient_name = str(parsed.get("creditor_name") or "").strip().strip("\"'“”‘’")
    if not recipient_name:
        return _transfer_response(
            _localize(
                language,
                "Tell me the saved contact's name and the amount to transfer, for example: “Transfer ¥50 to @Alex.”",
                "请告诉我已保存联系人的姓名和转账金额，例如：“Transfer ¥50 to @Alex.”",
            ),
            code="RECIPIENT_REQUIRED",
        )
    if not parsed.get("amount"):
        return _transfer_response(
            _localize(
                language,
                f"How much would you like to transfer to {recipient_name}?",
                f"你想向 {recipient_name} 转账多少？",
            ),
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
            _localize(
                language,
                f"More than one saved contact matches @{recipient_name.lstrip('@')}. "
                "Please specify the recipient's full name so I can identify the right person.",
                f"有多个已保存联系人匹配 @{recipient_name.lstrip('@')}。"
                "请提供收款人的完整姓名，以便我确认是哪一位。",
            ),
            code="RECIPIENT_AMBIGUOUS",
        )
    if recipient is None:
        return _transfer_response(
            _localize(
                language,
                f"@{recipient_name.lstrip('@')} is not in your saved contacts. Add them in Contacts before sending money.",
                f"@{recipient_name.lstrip('@')} 不在你的已保存联系人中。请先在联系人页面添加后再转账。",
            ),
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
            _localize(
                language,
                f"This transfer exceeds the FINN daily limit of CNY {hard_cap:,.0f}.",
                f"此转账超过 FINN 每日限额 CNY {hard_cap:,.0f}。",
            ),
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
            _localize(
                language,
                "Review the transfer details and confirm to continue.",
                "请检查转账信息并确认继续。",
            ),
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
            _localize(
                language,
                "This transfer confirmation expired. Start the transfer again.",
                "转账确认已过期，请重新发起转账。",
            ),
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
            _localize(
                language,
                "The transfer details changed. Start the transfer again to review the updated details.",
                "转账信息已变更，请重新发起并检查更新后的信息。",
            ),
            code="TRANSFER_DETAILS_CHANGED",
        )
    projected_daily_spend = daily_spend.spent_today() + amount
    if amount > hard_cap or projected_daily_spend > hard_cap:
        _PENDING_FINN_CONFIRMATIONS.pop(pending_key, None)
        return _transfer_response(
            _localize(
                language,
                f"This transfer exceeds the FINN daily limit of CNY {hard_cap:,.0f}.",
                f"此转账超过 FINN 每日限额 CNY {hard_cap:,.0f}。",
            ),
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
                _localize(
                    language,
                    "The daily total now requires additional verification. Enter the new code and confirm again.",
                    "当日累计金额现在需要额外验证。请输入新的验证码并再次确认。",
                ),
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
        _localize(
            language,
            "Transfer prepared. Approve to send the money.",
            "转账已准备，请批准后发送。",
        ),
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


@router.get("/agent/chat/history")
async def get_agent_chat_history(
    conversation_id: Optional[str] = Query(None, max_length=64),
    limit: int = Query(200, ge=1, le=500),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the durable transcript for one of the signed-in user's chats."""
    resolved = normalize_conversation_id(conversation_id) or latest_conversation_id(db, user.user_id)
    if not resolved:
        return {"conversation_id": None, "messages": []}
    messages = load_conversation(
        db,
        user_id=str(user.user_id),
        conversation_id=resolved,
        limit=limit,
    )
    return {
        "conversation_id": resolved,
        "messages": [
            {
                "id": item["id"],
                "role": item["role"],
                "content": item["content"],
                "intent": item["intent"],
                "created_at": item["created_at"],
            }
            for item in messages
        ],
    }


@router.delete("/agent/chat/history")
async def clear_agent_chat_history(
    conversation_id: Optional[str] = Query(None, max_length=64),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete one of the signed-in user's conversations."""
    resolved = normalize_conversation_id(conversation_id) or latest_conversation_id(db, user.user_id)
    if not resolved:
        return {"deleted_count": 0}
    return {
        "deleted_count": delete_conversation(
            db,
            user_id=str(user.user_id),
            conversation_id=resolved,
        )
    }


async def _agent_chat_turn(
    payload: AgentChatRequest,
    user: models.User,
    db: Session,
    language: str,
    history: list[dict[str, Any]],
) -> AgentChatResponse:
    """Compute one assistant reply; ``agent_chat`` persists the turn."""
    greeting = _greeting_reply(payload.message, language)
    if greeting:
        return AgentChatResponse(
            implemented=True,
            code="GREETING",
            message=greeting,
            rationale="Localized greeting",
            processing_mode="cfo-conversation",
        )

    # A short follow-up inherits the topic of the previous assistant turn.
    topic = last_topic(history)
    follow_up = bool(history) and is_follow_up(payload.message)

    # Balance data is factual, customer-scoped banking information. Resolve it
    # directly from FINN rather than asking an LLM to infer or fabricate it.
    if _is_balance_question(payload.message) or (follow_up and topic == "balance"):
        return AgentChatResponse(
            implemented=True,
            code="OK",
            operation_id="get-accounts",
            message=_balance_reply(user, language),
            rationale="Customer-scoped FINN account balance lookup",
            retrieved_operations=["get-accounts"],
            execution={"source": "finn", "customer_scoped": True},
            processing_mode="finn-direct",
        )
    transaction_summary = _transaction_summary_request(payload.message, history)
    if transaction_summary:
        direction, start_date, end_date = transaction_summary
        return AgentChatResponse(
            implemented=True,
            code="OK",
            operation_id="get-transactions-summary",
            message=_transaction_summary_reply(
                user, direction, start_date, end_date, language
            ),
            rationale="Customer-scoped FINN transaction summary",
            retrieved_operations=["get-transactions-summary"],
            execution={
                "source": "finn",
                "customer_scoped": True,
                "direction": direction,
                "period": period_from_message(payload.message) or "all_time",
                "start_date": start_date,
                "end_date": end_date,
            },
            processing_mode="finn-direct",
        )
    transfer_request = _is_transfer_request(payload.message) or (
        follow_up and topic == "transfer" and bool(_transfer_args(payload.message).get("amount"))
    )
    parsed_transfer = _transfer_args(payload.message) if transfer_request else {}
    transfer_context = (
        _transfer_context(payload.message, parsed_transfer, history) if follow_up else None
    )
    if transfer_context:
        transfer_request = True
    if transfer_request and parsed_transfer.get("amount") and parsed_transfer.get("creditor_name"):
        return await _handle_finn_transfer(payload, user, db)
    if transfer_request and transfer_context:
        return await _handle_finn_transfer(payload, user, db, transfer_context)
    interpreted_intent = interpret_cfo_intent(
        payload.message,
        payload.processing_mode,
        history,
        language,
    )
    if interpreted_intent and interpreted_intent["intent"] == "transfer":
        if interpreted_intent["confidence"] >= 0.6:
            return await _handle_finn_transfer(payload, user, db, interpreted_intent)
        return _transfer_response(
            _localize(
                language,
                "I may have misunderstood. If you want to make a transfer, please tell me the exact contact and amount.",
                "我可能理解错了。如需转账，请告诉我具体的联系人和金额。",
            ),
            code="TRANSFER_CLARIFICATION_REQUIRED",
        )
    if interpreted_intent and interpreted_intent["confidence"] >= 0.6:
        if interpreted_intent["intent"] == "balance":
            return AgentChatResponse(
                implemented=True,
                code="OK",
                operation_id="get-accounts",
                message=_balance_reply(user, language),
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
                message=_transaction_summary_reply(
                    user, direction, start_date, end_date, language
                ),
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
                message=_localize(
                    language,
                    "Are you asking about money coming into your accounts or money going out?",
                    "你问的是账户的进账还是支出？",
                ),
                rationale="AI-interpreted transaction summary needs a direction",
                retrieved_operations=["get-transactions-summary"],
                execution={"source": "finn", "customer_scoped": True},
                processing_mode="finn-direct",
            )
        if interpreted_intent["intent"] == "conversation":
            return AgentChatResponse(
                implemented=True,
                code="OK",
                message=_reply_in_language(
                    interpreted_intent.get("reply"),
                    language,
                    _localize(
                        language,
                        "I'm here to help. What would you like to know about your money?",
                        "我在。你想了解账户或收支的哪一方面？",
                    ),
                ),
                rationale="Natural-language CFO conversation",
                processing_mode="cfo-conversation",
            )
        if interpreted_intent["intent"] == "other":
            return AgentChatResponse(
                implemented=True,
                code="OUT_OF_SCOPE",
                message=_reply_in_language(
                    interpreted_intent.get("reply"),
                    language,
                    _out_of_scope_reply(language),
                ),
                rationale="Out-of-scope question handled without inventing data",
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
        history=history,
    )

    # The operation selector is allowed to say "not implemented", but the user
    # should get a capability answer, not a raw registry dump or a guess.
    if result.code == "NOT_IMPLEMENTED":
        return AgentChatResponse(
            implemented=False,
            code="OUT_OF_SCOPE",
            operation_id=result.operation_id,
            message=_out_of_scope_reply(language),
            rationale=result.selected.rationale,
            proposed_operation_id=result.selected.proposed_operation_id,
            retrieved_operations=result.retrieved,
            processing_mode=mode,
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


@router.post("/agent/chat", response_model=AgentChatResponse)
async def agent_chat(
    payload: AgentChatRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a message to the CFO chat and persist both sides of the turn.

    The transcript is stored in the application database and loaded again for
    every turn, so context survives the request, a page reload and a backend
    restart.  A follow-up always sees the earlier questions and answers.
    """
    language = detect_language(payload.message)
    conversation_id = normalize_conversation_id(payload.conversation_id) or new_conversation_id()
    session = db if hasattr(db, "query") else None
    history = (
        load_history(session, user_id=str(user.user_id), conversation_id=conversation_id)
        if session is not None
        else []
    )
    if session is not None:
        append_message(
            session,
            user_id=str(user.user_id),
            conversation_id=conversation_id,
            role="user",
            content=payload.message,
        )

    response = await _agent_chat_turn(payload, user, session, language, history)

    if session is not None:
        append_message(
            session,
            user_id=str(user.user_id),
            conversation_id=conversation_id,
            role="assistant",
            content=response.message,
            intent=_topic_for_response(response),
            message_metadata=_conversation_metadata(response),
        )
    response.conversation_id = conversation_id
    response.language = language
    return response


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
