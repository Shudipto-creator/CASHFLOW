"""An in-memory mock ledger implementing the bank2ai tool semantics.

This is the *bank*. It is intentionally the only place that owns mutable
financial state, so the tier rules and the okgate policy can be reasoned
about independently of it.

Modelling notes that matter for the security story:

* ``prepare-transfer`` validates and **reserves intent only** — no money moves.
  It is where the amount becomes known, which is why okgate's ``spend`` class
  and the ¥1,000 tier rule both attach here.
* ``execute-transfer`` takes only an intent id, moves the money, and is
  idempotent. A consumed intent cannot be executed twice, so a retry storm
  cannot double-spend.
* Every intent carries a TTL, mirroring a real bank's short-lived hold.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from uuid import uuid4

from bank2ai import (
    Account,
    AccountList,
    Category,
    CategoryList,
    CreateRecipientResponse,
    ExecuteTransferResponse,
    ExecutedTransfer,
    GetTransactionResponse,
    Party,
    PreparedTransfer,
    PrepareTransferResponse,
    Rail,
    Recipient,
    RecipientList,
    RemittanceInformation,
    Transaction,
    TransactionList,
    TransactionsSummary,
    TransactionsSummaryGroup,
    TransactionsSummaryPeriod,
    TransferAction,
    TransferExecutionStatus,
    TransferSummary,
)

from . import data as seed

# Fields dropped from a transaction at `verbosity="minimal"`.
_MINIMAL_SUPPRESSED_FIELDS = ("counterparty", "properties")

_DEFAULT_INTENT_TTL = timedelta(minutes=5)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Ledger:
    """Mutable mock bank state plus the bank2ai tool semantics."""

    def __init__(
        self,
        *,
        intent_ttl: timedelta = _DEFAULT_INTENT_TTL,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._lock = asyncio.Lock()
        self._ttl = intent_ttl
        self._now = clock

        self._accounts: dict[str, dict] = {a["id"]: dict(a) for a in seed.ACCOUNTS}
        self._transactions: list[dict] = seed.transactions()
        self._categories: list[dict] = [dict(c) for c in seed.CATEGORIES]
        self._recipients: dict[str, dict] = {r["id"]: dict(r) for r in seed.RECIPIENTS}

        self._intents: dict[str, PreparedTransfer] = {}
        self._executed_intents: set[str] = set()
        # Keyed by (tool, idempotency_key) so two tools cannot collide.
        self._idempotency: dict[tuple[str, str], object] = {}

    # -- idempotency ------------------------------------------------------

    def _cached(self, tool: str, key: Optional[str]) -> object | None:
        if key is None:
            return None
        return self._idempotency.get((tool, key))

    def _remember(self, tool: str, key: Optional[str], response: object) -> None:
        if key is not None:
            self._idempotency[(tool, key)] = response

    # -- reads ------------------------------------------------------------

    async def get_accounts(
        self,
        *,
        only_withdrawal_accounts: bool = False,
        account_type: Optional[str] = None,
        status: Optional[str] = None,
        usage: Optional[str] = None,
    ) -> AccountList:
        async with self._lock:
            rows = list(self._accounts.values())
        if only_withdrawal_accounts:
            rows = [a for a in rows if a.get("isWithdrawalAccount")]
        if account_type:
            rows = [a for a in rows if a.get("accountType") == account_type]
        if status:
            rows = [a for a in rows if a.get("status") == status]
        if usage:
            rows = [a for a in rows if a.get("usage") == usage]
        return AccountList(items=[Account(**a) for a in rows])

    async def get_transactions(
        self,
        *,
        count: Optional[int] = None,
        order: str = "NewestFirst",
        verbosity: str = "minimal",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search_text: Optional[str] = None,
        category_ids: Optional[list[str]] = None,
        account_ids: Optional[list[str]] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        cursor: Optional[str] = None,
    ) -> TransactionList:
        async with self._lock:
            rows = [dict(t) for t in self._transactions]

        if account_ids:
            wanted = set(account_ids)
            rows = [t for t in rows if t.get("accountId") in wanted]
        if start_date:
            rows = [t for t in rows if t["date"] >= start_date]
        if end_date:
            rows = [t for t in rows if t["date"] <= end_date]
        if min_amount is not None:
            rows = [t for t in rows if t["amount"] >= min_amount]
        if max_amount is not None:
            rows = [t for t in rows if t["amount"] <= max_amount]
        if category_ids:
            wanted_cats = set(category_ids)
            rows = [t for t in rows if t.get("categoryId") in wanted_cats]
        if search_text:
            needle = search_text.lower()

            def matches(t: dict) -> bool:
                candidates = [t.get("description") or "", t.get("originalDescription") or ""]
                candidates.append((t.get("counterparty") or {}).get("name") or "")
                candidates.extend(str(v) for v in (t.get("properties") or {}).values() if v)
                return any(needle in c.lower() for c in candidates if c)

            rows = [t for t in rows if matches(t)]

        rows.sort(key=lambda t: t["date"], reverse=(order == "NewestFirst"))

        try:
            offset = max(int(cursor), 0) if cursor else 0
        except ValueError:
            offset = 0
        if offset:
            rows = rows[offset:]

        next_cursor: Optional[str] = None
        if count is not None and len(rows) > count:
            next_cursor = str(offset + count)
            rows = rows[:count]

        return TransactionList(
            items=[self._apply_verbosity(Transaction(**t), verbosity) for t in rows],
            nextCursor=next_cursor,
        )

    async def get_transaction(
        self, *, transaction_id: str, account_id: Optional[str] = None
    ) -> GetTransactionResponse:
        async with self._lock:
            row = next((t for t in self._transactions if t.get("id") == transaction_id), None)
            row = dict(row) if row else None
        if row is None:
            return GetTransactionResponse(content=f"No transaction with id '{transaction_id}'.")
        if account_id is not None and row.get("accountId") != account_id:
            return GetTransactionResponse(
                content=f"Transaction '{transaction_id}' is not on account '{account_id}'."
            )
        return GetTransactionResponse(content="Transaction found.", item=Transaction(**row))

    async def get_categories(self) -> CategoryList:
        async with self._lock:
            rows = [dict(c) for c in self._categories]
        return CategoryList(items=[Category(**c) for c in rows])

    async def get_transactions_summary(
        self,
        *,
        direction: str,
        group_by: str = "category",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category_ids: Optional[list[str]] = None,
        account_ids: Optional[list[str]] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
    ) -> TransactionsSummary:
        async with self._lock:
            rows = [dict(t) for t in self._transactions]

        if account_ids:
            wanted = set(account_ids)
            rows = [t for t in rows if t.get("accountId") in wanted]
        rows = [t for t in rows if (t["amount"] < 0 if direction == "Expenses" else t["amount"] > 0)]
        if min_amount is not None:
            rows = [t for t in rows if t["amount"] >= min_amount]
        if max_amount is not None:
            rows = [t for t in rows if t["amount"] <= max_amount]
        if start_date:
            rows = [t for t in rows if t["date"] >= start_date]
        if end_date:
            rows = [t for t in rows if t["date"] <= end_date]
        if category_ids:
            wanted_cats = set(category_ids)
            rows = [t for t in rows if t.get("categoryId") in wanted_cats]

        def grouping_key(t: dict) -> tuple[Optional[str], Optional[str]]:
            category = t.get("categoryId")
            month = str(t["date"])[:7]
            if group_by == "category":
                return (category, None)
            if group_by == "month":
                return (None, month)
            if group_by == "both":
                return (category, month)
            return (None, None)

        groups: dict[tuple[Optional[str], Optional[str]], dict[str, float]] = defaultdict(
            lambda: {"total": 0.0, "count": 0.0}
        )
        for t in rows:
            bucket = groups[grouping_key(t)]
            bucket["total"] += t["amount"]
            bucket["count"] += 1

        summary = [
            TransactionsSummaryGroup(
                categoryId=category,
                month=month,
                totalAmount=stats["total"],
                transactionCount=int(stats["count"]),
                averageAmount=(stats["total"] / stats["count"]) if stats["count"] else 0.0,
            )
            for (category, month), stats in groups.items()
        ]
        summary.sort(key=lambda g: g.totalAmount)

        return TransactionsSummary(
            summary=summary,
            period=TransactionsSummaryPeriod(
                startDate=start_date or "all",
                endDate=end_date or "all",
            ),
            total=sum(g.totalAmount for g in summary),
        )

    async def get_recipients(self, *, name: str) -> RecipientList:
        needle = name.lower()
        async with self._lock:
            rows = [dict(r) for r in self._recipients.values()]
        return RecipientList(items=[Recipient(**r) for r in rows if needle in r["name"].lower()])

    # -- writes -----------------------------------------------------------

    async def create_recipient(
        self,
        *,
        name: str,
        account_identifier: dict,
        national_id: Optional[dict] = None,
        nickname: Optional[str] = None,
        bic: Optional[str] = None,
        default_description: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> CreateRecipientResponse:
        if (cached := self._cached("create-recipient", idempotency_key)) is not None:
            return cached  # type: ignore[return-value]

        async with self._lock:
            recipient_id = f"rcpt_{len(self._recipients) + 1:03d}"
            recipient = Recipient(
                id=recipient_id,
                name=name,
                accountIdentifier=account_identifier,
                nationalId=national_id,
                nickname=nickname,
                bic=bic,
                defaultDescription=default_description,
            )
            self._recipients[recipient_id] = recipient.model_dump(exclude_none=True)

        response = CreateRecipientResponse(
            content=f"Recipient '{name}' created successfully.",
            item=recipient,
        )
        self._remember("create-recipient", idempotency_key, response)
        return response

    async def prepare_transfer(
        self,
        *,
        debtor_account_id: str,
        creditor: dict,
        amount: float,
        currency: str,
        rail: str,
        local_instrument: Optional[str] = None,
        requested_execution_date: Optional[str] = None,
        remittance_information: Optional[dict] = None,
        end_to_end_id: Optional[str] = None,
        description: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> PrepareTransferResponse:
        if (cached := self._cached("prepare-transfer", idempotency_key)) is not None:
            return cached  # type: ignore[return-value]

        creditor_party = Party.model_validate(creditor)
        if creditor_party.accountIdentifier is None:
            return PrepareTransferResponse(
                content="creditor.accountIdentifier is required for routing.",
                code="missing_creditor_identifier",
            )

        async with self._lock:
            account_data = self._accounts.get(debtor_account_id)
            if account_data is None:
                return PrepareTransferResponse(
                    content=f"No debtor account with id '{debtor_account_id}'.",
                    code="invalid_account",
                )
            if account_data.get("availableBalance", 0.0) < amount:
                return PrepareTransferResponse(
                    content="Insufficient funds.",
                    code="insufficient_funds",
                )
            if currency != account_data.get("currency"):
                return PrepareTransferResponse(
                    content=(
                        f"Account '{debtor_account_id}' is denominated in "
                        f"{account_data.get('currency')}; a {currency} transfer needs "
                        "a cross-currency instruction, which this mock does not model."
                    ),
                    code="currency_mismatch",
                )

            debtor_account = Account(**account_data)
            now = self._now()
            intent_id = f"intent_{uuid4().hex}"
            summary = TransferSummary(
                debtorAccount=debtor_account,
                creditor=creditor_party,
                amount=amount,
                currency=currency,
                rail=Rail(rail),
                localInstrument=local_instrument,
                requestedExecutionDate=requested_execution_date,
                remittanceInformation=(
                    RemittanceInformation.model_validate(remittance_information)
                    if remittance_information
                    else None
                ),
                endToEndId=end_to_end_id or f"e2e_{uuid4().hex[:16]}",
                description=description,
            )
            prepared = PreparedTransfer(
                transferIntentId=intent_id,
                expiresAt=now + self._ttl,
                summary=summary,
            )
            self._intents[intent_id] = prepared

        response = PrepareTransferResponse(
            content=(
                "A transfer has been prepared. Confirm the details with the user, "
                "then call execute-transfer with the transferIntentId."
            ),
            item=prepared,
            actions=[TransferAction(title="Transfer", link="/transfer")],
        )
        self._remember("prepare-transfer", idempotency_key, response)
        return response

    async def execute_transfer(
        self,
        *,
        transfer_intent_id: str,
        idempotency_key: Optional[str] = None,
    ) -> ExecuteTransferResponse:
        if (cached := self._cached("execute-transfer", idempotency_key)) is not None:
            return cached  # type: ignore[return-value]

        async with self._lock:
            if transfer_intent_id in self._executed_intents:
                return ExecuteTransferResponse(
                    content=f"Transfer intent '{transfer_intent_id}' has already been executed.",
                    code="intent_already_executed",
                )
            intent = self._intents.get(transfer_intent_id)
            if intent is None:
                return ExecuteTransferResponse(
                    content=f"No such transfer intent '{transfer_intent_id}'.",
                    code="intent_not_found",
                )
            now = self._now()
            if now >= intent.expiresAt:
                return ExecuteTransferResponse(
                    content=(
                        f"Transfer intent '{transfer_intent_id}' expired at "
                        f"{intent.expiresAt.isoformat()}. Call prepare-transfer again."
                    ),
                    code="intent_expired",
                )

            # Settle: debit the debtor, append the ledger row, burn the intent.
            summary = intent.summary
            account_data = self._accounts[summary.debtorAccount.id]
            account_data["balance"] -= summary.amount
            account_data["availableBalance"] -= summary.amount
            account_data["balanceUpdatedAt"] = now.isoformat()
            self._executed_intents.add(transfer_intent_id)

            self._transactions.insert(
                0,
                {
                    "id": f"tx_{uuid4().hex[:12]}",
                    "accountId": summary.debtorAccount.id,
                    "description": summary.description or f"转账 — {summary.creditor.name}",
                    "amount": -summary.amount,
                    "date": now.date().isoformat(),
                    "categoryId": "Transfer",
                    "counterparty": summary.creditor.model_dump(exclude_none=True),
                    "properties": {"endToEndId": summary.endToEndId},
                },
            )

        response = ExecuteTransferResponse(
            content=(
                f"Transfer of {summary.amount:,.2f} {summary.currency} "
                "completed successfully."
            ),
            item=ExecutedTransfer(
                transactionId=f"tx_{uuid4().hex[:12]}",
                status=TransferExecutionStatus.Settled,
                executedAt=now,
            ),
        )
        self._remember("execute-transfer", idempotency_key, response)
        return response

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _apply_verbosity(transaction: Transaction, verbosity: str) -> Transaction:
        """At `minimal`, drop the heavy optional objects.

        Unset optional keys are elided from the wire payload, so the
        suppressed objects are simply absent rather than null.
        """
        if verbosity == "full":
            return transaction
        for field in _MINIMAL_SUPPRESSED_FIELDS:
            setattr(transaction, field, None)
        return transaction
