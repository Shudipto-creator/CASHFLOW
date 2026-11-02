"""Bank adapter for the Postman Banking-API-Demo (functional sandbox).

Where this sits in the Zero-Trust architecture
----------------------------------------------
    agent / frontend
        -> okgate proxy  (tiers, caps, loop breaker, kill switch, audit)
            -> SecureBankGate (MFA + confirmation + spend ledger)
                -> bank2ai MCP tools          <- tool names never change here
                    -> Ledger | PostmanBank   <- this file plugs in *here*

The adapter is deliberately *behind* the gate. It owns no policy: it cannot see
or influence tier classification, and the gate never trusts what it returns.
That is what makes the swap provably safe — the same okgate.yaml, the same
SecureBankGate and the same bank2ai tool surface drive a hand-written mock and
a live stateful REST API, so a passing security demo means the same thing for
both.

backend-agnostic note
---------------------
`build_server()` keeps the tool names and response models from bank2ai. Only the
source of the data changes, which is the contract a real bank integration would
have to satisfy anyway.
"""

from __future__ import annotations

import asyncio
import base64
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel
from enum import Enum

from ..config import PostmanDemoSettings, get_postman_settings
from .ledger import Ledger

# Exact wording required for the failsafe: an operator reading the UI must know
# the sandbox is simply not up, not that a transfer was refused by policy.
DEMO_UNAVAILABLE_MESSAGE = (
    "Postman Demo API is not running. Please start it with `npm run dev`."
)

_DEFAULT_INTENT_TTL = timedelta(minutes=5)


def _httpx():
    """Import httpx on first use instead of at module import.

    Cold-importing httpx costs ~4s on this stack, measured as the whole
    difference between the mock upstream starting in 8s and the Postman upstream
    starting in 12s — against okgate's hard 15s budget for the upstream MCP
    handshake. `tools/list` needs no HTTP client, so the library is loaded when
    the first request is made rather than while the proxy is waiting.
    """
    import httpx

    return httpx


class ToolStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


class ToolResult(BaseModel):
    """Standardised envelope every adapter call returns.

    `status` is the transport outcome, `data` the decoded payload, `message` a
    human-readable summary. A failed call never fabricates `data`: an empty list
    with status="error" would be indistinguishable from a genuinely empty account
    list, which is exactly the kind of ambiguity a security review should reject.
    """

    status: str = ToolStatus.OK
    message: str = ""
    data: Any = None
    source: str = "postman_demo"
    detail: Optional[str] = None

    @classmethod
    def ok(cls, data: Any, message: str = "", **meta: Any) -> "ToolResult":
        return cls(status=ToolStatus.OK, data=data, message=message, **meta)

    @classmethod
    def error(cls, message: str, detail: Optional[str] = None, **meta: Any) -> "ToolResult":
        return cls(status=ToolStatus.ERROR, message=message, data=None, detail=detail, **meta)

    @property
    def ok_flag(self) -> bool:
        return self.status == ToolStatus.OK


class BankUnavailableError(RuntimeError):
    """Transport failure while talking to the configured bank sandbox.

    Raised (not swallowed) on the bank2ai surface: per the handler contract in
    bank/server.py, transport-level failures must raise so the gate records a
    refusal instead of a completed money movement. Failing closed is the
    Zero-Trust behaviour; returning a plausible-looking empty result is not.
    """


def _pick(row: dict, *names: str, default: Any = None) -> Any:
    """First present key among `names`.

    The demo's JSON uses camelCase for some resources and snake_case for others,
    and the exact field set could not be enumerated offline (no egress from this
    machine to GitHub), so reads stay tolerant instead of brittle.
    """
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return default


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_minor_units(amount: float, scale: int = 1) -> int:
    """Convert an amount exactly to the upstream's integer currency unit.

    The sandbox currencies have exponent zero, so its default scale is one.
    Legacy two-decimal APIs can explicitly configure a scale of 100. Reject
    amounts that cannot be represented rather than silently rounding a transfer.
    """
    try:
        value = Decimal(str(amount))
        scaled = value * scale
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Transfer amount must be a finite positive number.") from exc
    if not value.is_finite() or value <= 0 or scaled != scaled.to_integral_value():
        raise ValueError(
            "Transfer amount must be positive and exactly representable in the sandbox currency."
        )
    return int(scaled)


def from_minor_units(value: Any, scale: int = 1) -> float:
    """Convert an upstream integer amount into the gate's amount unit."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Sandbox amount must be a finite number.") from exc
    if not amount.is_finite():
        raise ValueError("Sandbox amount must be a finite number.")
    return round(float(amount / scale), 6)


class PostmanBankClient:
    """Thin async httpx wrapper over the Postman Banking-API-Demo.

    One client per request is fine (the demo is stateless between calls apart
    from its in-memory ledger); `aclose()` keeps connection pooling available to
    callers that hold the client open.
    """

    def __init__(
        self,
        settings: Optional[PostmanDemoSettings] = None,
        *,
        transport: Optional[Any] = None,  # httpx.AsyncBaseTransport, deferred import
    ) -> None:
        self.settings = settings or get_postman_settings()
        self._headers = {
            "x-api-key": self.settings.api_key,  # demo default customer key
            "content-type": "application/json",
        }
        if self.settings.run_id:
            # The demo keeps independent ledgers per run id (X-Demo-Run-Id), so a
            # fresh run can be reset without disturbing another demo.
            self._headers["x-demo-run-id"] = self.settings.run_id
        self._transport = transport
        self._client: Optional[Any] = None

    def _http(self) -> Any:
        """Build the httpx client on first request, never at construction.

        okgate gives the upstream it spawns 15s to finish the MCP handshake
        (hard-coded `connectTimeoutMs: 15e3`), and measured on this stack,
        `httpx.AsyncClient()` costs ~7s because it eagerly builds a TLS context
        from the OS certificate store. The bank server is launched per run, so
        that cost landed inside the handshake and the proxy answered
        "no upstream exposes a tool named ..." for the whole run. Nothing needs
        TLS until a call is actually made, so neither does the constructor.
        """
        if self._client is None:
            httpx = _httpx()
            self._client = httpx.AsyncClient(
                timeout=self.settings.timeout_s,
                headers=self._headers,
                transport=self._transport,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, url: str, params: Optional[dict] = None) -> ToolResult:
        httpx = _httpx()
        try:
            response = await self._http().get(url, params=params)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            # Failsafe required by the spec: friendly, and no fabricated data.
            return ToolResult.error(DEMO_UNAVAILABLE_MESSAGE, detail=repr(exc), url=url)
        except httpx.TimeoutException as exc:
            return ToolResult.error(
                f"Postman Demo API did not respond within {self.settings.timeout_s}s.",
                detail=repr(exc),
                url=url,
            )
        except httpx.HTTPStatusError as exc:
            # 401 here means the x-api-key is wrong, not that the service is down.
            return ToolResult.error(
                f"Postman Demo API returned {exc.response.status_code}.",
                detail=exc.response.text[:500],
                url=url,
            )
        except httpx.HTTPError as exc:
            return ToolResult.error("Postman Demo API request failed.", detail=repr(exc), url=url)
        try:
            return ToolResult.ok(response.json(), url=url)
        except ValueError:
            return ToolResult.error(
                "Postman Demo API returned a non-JSON body.",
                detail=response.text[:500],
                url=url,
            )

    async def _post(
        self, url: str, payload: dict, *, idempotency_key: Optional[str] = None
    ) -> ToolResult:
        httpx = _httpx()
        headers = {}
        if idempotency_key:
            # The demo replays a request with the same Idempotency-Key, so a retry
            # after a timeout cannot double-post the transfer.
            headers["Idempotency-Key"] = idempotency_key
        try:
            response = await self._http().post(url, json=payload, headers=headers)
            response.raise_for_status()
        except httpx.ConnectError as exc:
            return ToolResult.error(DEMO_UNAVAILABLE_MESSAGE, detail=repr(exc), url=url)
        except httpx.TimeoutException as exc:
            return ToolResult.error(
                f"Postman Demo API timed out while committing the transfer after "
                f"{self.settings.timeout_s}s.",
                detail=repr(exc),
                url=url,
            )
        except httpx.HTTPStatusError as exc:
            return ToolResult.error(
                f"Postman Demo API rejected the transfer with {exc.response.status_code}.",
                detail=exc.response.text[:500],
                url=url,
            )
        except httpx.HTTPError as exc:
            return ToolResult.error(
                "Postman Demo transfer request failed.", detail=repr(exc), url=url
            )
        try:
            return ToolResult.ok(response.json(), url=url)
        except ValueError:
            return ToolResult.error(
                "Postman Demo API returned a non-JSON body for the transfer.",
                detail=response.text[:500],
                url=url,
            )

    # -- the three functions the integration brief names ------------------

    async def get_accounts(self) -> ToolResult:
        """GET {base}{prefix}/accounts with the x-api-key header."""
        return await self._get(self.settings.accounts_url)

    async def get_transactions(self, *, count: Optional[int] = None) -> ToolResult:
        """GET {base}{prefix}/transactions with the x-api-key header."""
        params = {"limit": count} if count else None
        return await self._get(self.settings.transactions_url, params=params)

    async def get_beneficiaries(self) -> ToolResult:
        """GET the authenticated customer's saved recipients."""
        return await self._get(self.settings.beneficiaries_url)

    async def execute_transfer(
        self,
        amount: float,
        to_account: Any,
        *,
        currency: Optional[str] = None,
        from_account: Optional[str] = None,
        description: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> ToolResult:
        """POST the transfer to the demo API.

        Contract verified from the demo's own OpenAPI CreateTransactionRequest:
        `fromAccountId`, `toAccountId`, `amount`, `currency` are required, amounts
        are *integers in the configured currency units*, and `additionalProperties: false` means any
        extra key is a 400 — hence the explicit field list instead of merging a
        caller dict into the body.

        `amount` is accepted in the gate's configured unit and converted using
        the upstream amount scale.

        See `PostmanBankBackend.prepare_transfer` for why the MCP tool surface must
        *not* call this directly.
        """
        if self.settings.read_only:
            return ToolResult.error("Transfers are disabled for this read-only FINN demo connection.")
        to_id = (
            _pick(
                to_account,
                "identification",
                "accountNumber",
                "accountId",
                "id",
                default=None,
            )
            if isinstance(to_account, dict)
            else to_account
        )
        try:
            amount_units = to_minor_units(amount, self.settings.amount_scale)
        except ValueError as exc:
            return ToolResult.error("Transfer amount is invalid.", detail=str(exc))
        payload: dict[str, Any] = {
            "toAccountId": str(to_id),
            "amount": amount_units,
            "currency": currency or self.settings.currency,
        }
        if from_account:
            payload["fromAccountId"] = str(from_account)
        if description:
            payload["description"] = description
        return await self._post(
            self.settings.transfer_url, payload, idempotency_key=idempotency_key
        )


# -- bank2ai model mapping --------------------------------------------------


def _to_bank2ai_currency(demo_currency: str) -> str:
    """Map the demo's fictional currency onto bank2ai's `^[A-Z]{3}$` pattern.

    bank2ai validates currency as a three-letter code, and the demo's enum
    (COSMIC_COINS / GALAXY_GOLD / MOON_BUCKS) has no ISO code at all, so the
    first three letters are used as a *display* convention. The real value is
    carried separately (`_api_currency`) and is what goes on the wire — a
    transfer must never be posted as "COS".
    """
    return str(demo_currency)[:3].upper()


# The demo's status/product vocabularies have no bank2ai equivalents: its enum is
# ACTIVE/INACTIVE against bank2ai's Enabled/Blocked/Deleted, and its
# STANDARD/PREMIUM/BUSINESS tiers are not a product taxonomy. Anything unmapped
# becomes "Other" rather than an invented account type, so a filter like
# account_type="Current" simply matches nothing instead of lying.
_STATUS_MAP = {"ACTIVE": "Enabled", "INACTIVE": "Blocked"}


def _to_account_dict(row: dict, *, amount_scale: int = 1) -> dict:
    """Map a demo Account onto bank2ai's Account.

    Field names are the demo's own (openapi.yaml `Account`: accountId, owner,
    accountType, createdAt, balance, currency, status). Four adaptations matter:

    * the demo has no `accountNumber`, but bank2ai requires it, so the demo's
      `accountId` is reused as the display identifier — the value a transfer must
      name as `toAccountId`;
    * the demo has one `balance` (no available/held split), so both bank2ai
      balance fields carry the same amount in the configured unit scale;
    * currency and status go through the maps above to satisfy bank2ai's stricter
      enums, while `_api_currency` keeps the value the HTTP body needs;
    * `owner` becomes the account name, the only human-readable handle the demo
      offers.
    """
    account_id = str(_pick(row, "accountId", "account_id", "id", default="unknown"))
    balance = from_minor_units(_pick(row, "balance", default=0), amount_scale)
    status = _pick(row, "status")
    return {
        "id": account_id,
        "accountNumber": str(_pick(row, "accountNumber", "number", default=account_id)),
        "currency": _to_bank2ai_currency(_api_currency_of(row)),
        "balance": balance,
        "availableBalance": balance,
        "name": _pick(row, "name", "label", "owner") or account_id,
        # Preserve the sandbox's own account type for FINN's account summary UI.
        "product": _pick(row, "product", "accountType"),
        # No bank2ai product taxonomy corresponds to STANDARD/PREMIUM/BUSINESS.
        "accountType": "Other",
        "status": _STATUS_MAP.get(str(status), "Enabled"),
    }


def _api_currency_of(row: dict) -> str:
    """The demo's real currency string, which is what the HTTP body must carry."""
    return str(_pick(row, "currency", default="COSMIC_COINS"))


def _to_transaction_dict(
    row: dict,
    default_account_id: str = "unknown",
    our_account_ids: Optional[set] = None,
    amount_scale: int = 1,
) -> dict:
    """Map a demo Transaction onto bank2ai's Transaction.

    The demo stores every amount as a non-negative integer and expresses direction
    through `fromAccountId` / `toAccountId`; bank2ai expects a signed amount
    (expenses negative), so the sign is derived from which side is ours. Without
    this, outflows would render as income in the dashboard and Ask-CFO answers.
    """
    our_ids = our_account_ids or set()
    from_id = str(_pick(row, "fromAccountId", "from_account_id", default=""))
    to_id = str(_pick(row, "toAccountId", "to_account_id", default=""))
    magnitude = from_minor_units(_pick(row, "amount", default=0), amount_scale)
    is_outflow = bool(our_ids) and from_id in our_ids and to_id not in our_ids
    account_id = to_id if (to_id in our_ids) else (from_id or default_account_id)
    return {
        "id": str(_pick(row, "transactionId", "transaction_id", "id", default=uuid4().hex[:12])),
        "accountId": account_id or default_account_id,
        "description": str(
            _pick(row, "description", "memo", "narrative", default="")
            or _pick(row, "beneficiaryName", default="")
            or ""
        ),
        "amount": -magnitude if is_outflow else magnitude,
        "date": str(
            _pick(
                row,
                "createdAt",
                "created_at",
                "date",
                "postedAt",
                default=_utcnow().isoformat(),
            )[:10]
        ),
        "categoryId": _pick(row, "categoryId", "category", "category_id"),
    }


# bank2ai's Party.accountIdentifier is a union of identifier shapes; these are the
# keys that can carry the actual destination, most-specific first.
_IDENTIFIER_KEYS = (
    "accountId",
    "identification",
    "accountNumber",
    "iban",
    "bban",
    "msisdn",
    "email",
    "id",
)


def _identifier_text(party: Any) -> str:
    identifier = getattr(party, "accountIdentifier", party)
    if identifier is None:
        return ""
    if isinstance(identifier, str):
        return identifier
    data = (
        identifier.model_dump(exclude_none=True)
        if hasattr(identifier, "model_dump")
        else identifier
    )
    if not isinstance(data, dict):
        return str(data)
    return str(_pick(data, *_IDENTIFIER_KEYS, default="") or "")


def _normalize_identifier(value: str) -> str:
    """Compare identifiers ignoring the display spacing real banks add."""
    return value.replace(" ", "").replace("-", "").upper()


def _resolve_to_account_id(party: Any, rows: list[dict]) -> Optional[str]:
    """Map a bank2ai creditor onto an account the sandbox actually holds.

    Done at prepare time on purpose: the demo 400s on an unknown `toAccountId`,
    and failing here means the gate never carries an approval or an MFA release
    for a transfer that could not be posted.
    """
    text = _identifier_text(party)
    if not text:
        return None
    wanted = _normalize_identifier(text)
    for row in rows:
        for key in _IDENTIFIER_KEYS:
            value = _pick(row, key)
            if value is not None and _normalize_identifier(str(value)) == wanted:
                return str(_pick(row, "accountId", "account_id", "id", default=value))
    return None


def _signed_intent(settings: PostmanDemoSettings, data: dict[str, Any]) -> str:
    """Pack transfer details into an authenticated, restart-safe intent token.

    The MCP upstream is short-lived for each app request, so an in-memory intent
    disappears between preparation and approval. A signed token lets a later
    upstream instance recover the exact approved details without trusting
    caller-edited account or amount fields.
    """
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = hmac.new(settings.api_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"finn_{encoded}.{signature}"


def _open_signed_intent(settings: PostmanDemoSettings, token: str) -> Optional[dict[str, Any]]:
    try:
        encoded, signature = token.removeprefix("finn_").rsplit(".", 1)
        expected = hmac.new(settings.api_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        data = json.loads(payload)
        if not isinstance(data, dict) or int(data.get("expires", 0)) <= int(_utcnow().timestamp()):
            return None
        return data
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


class PostmanBankBackend:
    """bank2ai-shaped bank backed by the Postman demo REST API.

    Keeps the two-phase prepare/execute split even though the demo exposes a
    one-shot transfer, and this is the security-critical part of the file:

    okgate.yaml classifies `prepare-transfer` as the spend class
    (`spend.tools.prepare-transfer.amount_arg: amount`) and treats
    `execute-transfer` as "irreversible, but not priceable from their
    arguments". The daily ¥5,000 cap and the ¥1,000 Yellow / Red tier rules are
    therefore derived from the *prepare* call. If an MCP tool named
    e.g. `postman-transfer` moved money in a single call, okgate would have no
    priced amount to charge, and a compromised agent could drain past the caps
    while every audit row still looked compliant. So: prepare reserves and is
    priced here without touching the network; execute is the only call that
    commits money, and it is the only path that reaches the demo's
    `POST /api/v1/transactions`.
    """

    def __init__(
        self,
        client: Optional[PostmanBankClient] = None,
        *,
        fallback: Optional[Ledger] = None,
        intent_ttl: timedelta = _DEFAULT_INTENT_TTL,
    ) -> None:
        self.client = client or PostmanBankClient()
        # Tools the demo does not model (categories, recipients, summaries) keep
        # answering from the in-memory ledger, so the MCP surface stays complete
        # instead of disappearing mid-demo.
        self._fallback = fallback or Ledger()
        self._ttl = intent_ttl
        self._intents: dict[str, dict] = {}
        self._executed: set[str] = set()
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self.client.aclose()

    async def _rows(self, result: ToolResult, key: str) -> list[dict]:
        """Normalise the demo's list-vs-wrapped responses into rows.

        Raises rather than returning [] on a failed call — an unreachable bank
        must not be indistinguishable from an account with no history.
        """
        if not result.ok_flag:
            raise BankUnavailableError(f"{result.message} (detail: {result.detail})")
        payload = result.data
        if isinstance(payload, dict):
            rows = payload.get(key) or payload.get("data") or payload.get("items") or []
        elif isinstance(payload, list):
            rows = payload
        else:
            rows = []
        return [r for r in rows if isinstance(r, dict)]

    # -- reads ------------------------------------------------------------

    async def _our_account_ids(self) -> set:
        """Account ids visible to this API key, used to sign transaction amounts.

        Degrades to an empty set (unsigned amounts) rather than failing the read:
        a transaction list is still useful if the account lookup is briefly down,
        and `get_transactions` is a Green-tier read that must not become a
        second point of failure.
        """
        try:
            rows = await self._rows(await self.client.get_accounts(), "accounts")
        except BankUnavailableError:
            return set()
        return {str(_pick(r, "accountId", "account_id", "id")) for r in rows}

    async def get_accounts(self, **_: Any):
        from bank2ai import Account, AccountList

        rows = await self._rows(await self.client.get_accounts(), "accounts")
        scale = self.client.settings.amount_scale
        return AccountList(items=[Account(**_to_account_dict(r, amount_scale=scale)) for r in rows])

    async def get_recipients(self, *, name: str):
        """Return only trusted, in-sandbox beneficiaries for the current key."""
        from bank2ai import AccountNumberIdentifier, Recipient, RecipientList

        rows = await self._rows(await self.client.get_beneficiaries(), "beneficiaries")
        needle = (name or "").strip().casefold()
        matches = []
        for row in rows:
            account_id = _pick(row, "accountId", "account_id")
            recipient_name = str(_pick(row, "name", default="")).strip()
            if (
                str(_pick(row, "status", default="")).upper() != "TRUSTED"
                or not account_id
                or (needle and needle not in recipient_name.casefold())
            ):
                continue
            matches.append(Recipient(
                id=str(_pick(row, "beneficiaryId", "id", default=account_id)),
                name=recipient_name,
                accountIdentifier=AccountNumberIdentifier(
                    accountNumber=str(account_id), country="CN"
                ),
            ))
        return RecipientList(items=matches)

    async def get_transactions(self, **filters: Any):
        from bank2ai import Transaction, TransactionList

        ours = await self._our_account_ids()
        rows = await self._rows(await self.client.get_transactions(), "transactions")
        scale = self.client.settings.amount_scale
        items = [Transaction(**_to_transaction_dict(r, our_account_ids=ours, amount_scale=scale)) for r in rows]
        count = filters.get("count")
        if isinstance(count, int) and count >= 0:
            items = items[:count]
        return TransactionList(items=items, nextCursor=None)

    async def get_transaction(self, *, transaction_id: str, account_id: Optional[str] = None):
        rows = await self._rows(await self.client.get_transactions(), "transactions")
        ours = await self._our_account_ids()
        from bank2ai import GetTransactionResponse, Transaction

        for row in rows:
            mapped = _to_transaction_dict(
                row, our_account_ids=ours, amount_scale=self.client.settings.amount_scale
            )
            if mapped["id"] == transaction_id:
                return GetTransactionResponse(
                    content="Transaction found.", item=Transaction(**mapped)
                )
        return GetTransactionResponse(content=f"No transaction with id '{transaction_id}'.")

    # -- writes -----------------------------------------------------------

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
    ):
        """Reserve and price the intent; makes no network call.

        Validation mirrors the mock (unknown debtor, insufficient funds, currency
        mismatch) so gate-side tier decisions see identical business codes from
        either backend.
        """
        from bank2ai import (
            Account,
            PreparedTransfer,
            PrepareTransferResponse,
            Rail,
            TransferAction,
            TransferSummary,
        )
        from bank2ai import Party

        if self.client.settings.read_only:
            return PrepareTransferResponse(
                content="Transfers are disabled for this read-only FINN demo connection.",
                code="read_only",
            )

        try:
            to_minor_units(amount, self.client.settings.amount_scale)
        except ValueError as exc:
            return PrepareTransferResponse(
                content=str(exc),
                code="invalid_amount",
            )

        creditor_party = Party.model_validate(creditor)
        if creditor_party.accountIdentifier is None:
            return PrepareTransferResponse(
                content="creditor.accountIdentifier is required for routing.",
                code="missing_creditor_identifier",
            )
        supplied_account_id = getattr(
            creditor_party.accountIdentifier, "accountNumber", None
        )
        if not supplied_account_id:
            return PrepareTransferResponse(
                content="creditor.accountIdentifier.accountNumber is required for routing.",
                code="missing_creditor_identifier",
            )

        rows = await self._rows(await self.client.get_accounts(), "accounts")
        account_row = next(
            (
                r
                for r in rows
                if str(_pick(r, "id", "accountId", "account_id")) == debtor_account_id
            ),
            None,
        )
        if account_row is None:
            return PrepareTransferResponse(
                content=f"No debtor account with id '{debtor_account_id}'.",
                code="invalid_account",
            )
        mapped = _to_account_dict(
            account_row, amount_scale=self.client.settings.amount_scale
        )
        if mapped["availableBalance"] < amount:
            return PrepareTransferResponse(content="Insufficient funds.", code="insufficient_funds")

        # The sandbox has no CNY — its enum is COSMIC_COINS/GALAXY_GOLD/MOON_BUCKS,
        # shown to the agent as the 3-letter display code bank2ai requires. Both
        # spellings are accepted here. Refusing an unknown currency is the default
        # so nobody accidentally runs the ¥1,000 / ¥5,000 tiers against a token the
        # bank does not price. With POSTMAN_DEMO_ALLOW_CURRENCY_ALIAS=1 the
        # caller's label is treated as decorative and the amount is committed in
        # the account's own unit — a functional demo of the flow, not a
        # monetary-accurate one.
        settlement_currency = _api_currency_of(account_row)
        if (
            currency not in {mapped["currency"], settlement_currency}
            and not self.client.settings.allow_currency_alias
        ):
            return PrepareTransferResponse(
                content=(
                    f"Account '{debtor_account_id}' is denominated in {settlement_currency}; "
                    f"a {currency} transfer needs a cross-currency instruction the sandbox "
                    "does not model. Set POSTMAN_DEMO_CURRENCY / "
                    "POSTMAN_DEMO_ALLOW_CURRENCY_ALIAS=1 to run functionally."
                ),
                code="currency_mismatch",
            )

        # A customer key cannot list another customer's accounts. Resolve the
        # destination through the sender's trusted beneficiary list instead; the
        # sandbox transaction endpoint then independently verifies that account
        # exists, is active, and has a matching currency.
        beneficiaries = await self._rows(
            await self.client.get_beneficiaries(), "beneficiaries"
        )
        trusted_matches = [
            row
            for row in beneficiaries
            if str(_pick(row, "status", default="")).upper() == "TRUSTED"
            and str(_pick(row, "name", default="")).strip().casefold()
            == creditor_party.name.strip().casefold()
            and _pick(row, "accountId", "account_id")
        ]
        if len(trusted_matches) != 1:
            return PrepareTransferResponse(
                content=(
                    f"Expected one trusted sandbox recipient named '{creditor_party.name}', "
                    f"found {len(trusted_matches)}. Verify the saved recipient first."
                ),
                code="unknown_recipient",
            )
        to_account_id = str(_pick(trusted_matches[0], "accountId", "account_id"))
        if str(supplied_account_id) != to_account_id:
            return PrepareTransferResponse(
                content="The supplied account does not match the customer's trusted recipient record.",
                code="recipient_identifier_mismatch",
            )

        now = _utcnow()
        expires_at = now + self._ttl
        summary = TransferSummary(
            debtorAccount=Account(**mapped),
            creditor=creditor_party,
            amount=amount,
            # bank2ai validates currency as ^[A-Z]{3}$, so the intent shows the
            # display code while the API body keeps COSMIC_COINS. The wire value
            # is carried in the private intent below, never in this model.
            currency=mapped["currency"],
            rail=Rail(rail),
            localInstrument=local_instrument,
            requestedExecutionDate=requested_execution_date,
            endToEndId=end_to_end_id or f"e2e_{uuid4().hex[:16]}",
            description=description,
        )
        intent_id = _signed_intent(self.client.settings, {
            "from": debtor_account_id,
            "to": to_account_id,
            "amount": amount,
            "currency": settlement_currency,
            "description": description,
            "name": creditor_party.name,
            "expires": int(expires_at.timestamp()),
        })
        prepared = PreparedTransfer(
            transferIntentId=intent_id,
            expiresAt=expires_at,
            summary=summary,
        )
        return PrepareTransferResponse(
            content=(
                "A transfer has been prepared against the Postman demo bank. Confirm the "
                "details with the user, then call execute-transfer with the transferIntentId."
            ),
            item=prepared,
            actions=[TransferAction(title="Transfer", link="/transfer")],
        )

    async def execute_transfer(
        self, *, transfer_intent_id: str, idempotency_key: Optional[str] = None
    ):
        """Commit a previously priced intent — the only money-moving call here."""
        from bank2ai import ExecutedTransfer, ExecuteTransferResponse, TransferExecutionStatus

        if self.client.settings.read_only:
            return ExecuteTransferResponse(
                content="Transfers are disabled for this read-only FINN demo connection.",
                code="read_only",
            )

        intent = _open_signed_intent(self.client.settings, transfer_intent_id)
        if intent is None:
            return ExecuteTransferResponse(
                content="Transfer details are invalid or the prepared transfer has expired.",
                code="intent_invalid_or_expired",
            )

        result = await self.client.execute_transfer(
            intent["amount"],
            intent["to"],
            currency=intent["currency"],
            from_account=intent["from"],
            description=intent["description"],
            idempotency_key=idempotency_key or (
                "finn-" + hashlib.sha256(transfer_intent_id.encode()).hexdigest()
            ),
        )
        if not result.ok_flag:
            # The gate has already approved this call; report a business failure
            # with a code rather than pretending settlement succeeded.
            return ExecuteTransferResponse(
                content=f"{result.message} {result.detail or ''}".strip(),
                code="bank_unavailable",
            )

        raw = result.data if isinstance(result.data, dict) else {}
        # The demo answers {"transaction": {...}} for a posted transaction; the
        # id may also come back unwrapped depending on the route version.
        payload = raw.get("transaction") if isinstance(raw.get("transaction"), dict) else raw
        return ExecuteTransferResponse(
            content=(
                f"Transfer of {intent['amount']:,.0f} {intent['currency']} "
                "completed successfully."
            ),
            item=ExecutedTransfer(
                transactionId=str(
                    _pick(payload, "transactionId", "id", "transferId", default=uuid4().hex[:12])
                ),
                status=TransferExecutionStatus.Settled,
                executedAt=_utcnow(),
            ),
        )

    # -- tools the demo does not model: delegate to the in-memory ledger ---

    def __getattr__(self, name: str):
        return getattr(self._fallback, name)
