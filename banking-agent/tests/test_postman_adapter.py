"""Adapter tests for the Postman Banking-API-Demo sandbox.

The fixtures mirror the demo's *verified* contract, read from its own
`apps/banking-api/openapi/openapi.yaml` and `src/server.js`:

* routers mount under ``/api/v1``;
* auth is the ``x-api-key`` header, default customer key ``1234``;
* there is **no transfers route** — a money movement is
  ``POST /api/v1/transactions`` ("Post an atomic transfer or deposit") with
  required ``fromAccountId``/``toAccountId``/``amount``/``currency``;
* every monetary value is a **non-negative integer in minor units**, and the
  currency enum is COSMIC_COINS / GALAXY_GOLD / MOON_BUCKS (no CNY);
* errors use the ``{error: {name, message}}`` envelope, and the 201 body wraps the
  transaction in ``{transaction: ...}`` — the stub replays both shapes.

Two things follow for CI:

* We cannot depend on the Node service being up, so the default tests drive an
  in-process `httpx.MockTransport` replaying that contract — including its
  `additionalProperties: false` rule, which is what would 400 a wrong payload.
* One test (``test_live_demo_*``) exercises the *real* server when
  ``POSTMAN_DEMO_LIVE=1`` is set, which is the check to run for the demo.
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

from banking_agent.bank.postman_adapter import (
    DEMO_UNAVAILABLE_MESSAGE,
    BankUnavailableError,
    PostmanBankBackend,
    PostmanBankClient,
    ToolResult,
    from_minor_units,
    to_minor_units,
)

DEBTOR = "acct-001"
RECIPIENT = "acct-002"
CREDITOR = {
    "name": "李娜",
    "accountIdentifier": {
        "type": "accountNumber",
        "accountNumber": RECIPIENT,
        "country": "CN",
    },
}

# Demo-shaped rows (minor units, its own field names) — not bank2ai rows.
_DEMO_ACCOUNTS = [
    {
        "accountId": DEBTOR,
        "owner": "cust-001",
        "accountType": "PREMIUM",
        "createdAt": "2026-01-04",
        "balance": 12_845_000,  # 128,450.00 in minor units
        "currency": "COSMIC_COINS",
        "status": "ACTIVE",
    },
    {
        "accountId": RECIPIENT,
        "owner": "cust-002",
        "accountType": "STANDARD",
        "createdAt": "2026-02-11",
        "balance": 5_000_00,
        "currency": "COSMIC_COINS",
        "status": "ACTIVE",
    },
    {
        "accountId": "acct-003",
        "owner": "cust-001",
        "accountType": "BUSINESS",
        "createdAt": "2026-03-02",
        "balance": 0,
        "currency": "GALAXY_GOLD",
        "status": "ACTIVE",
    },
]

_DEMO_TRANSACTIONS = [
    {
        "transactionId": "TX-1042",
        "createdAt": "2026-10-30T09:15:00Z",
        "amount": 6_800,  # outflow of 68.00, stored unsigned
        "currency": "COSMIC_COINS",
        "fromAccountId": DEBTOR,
        "toAccountId": "merchant-starbucks",
        "status": "POSTED",
        "description": "星巴克",
        "beneficiaryName": "Starbucks",
        "channel": "MOBILE_APP",
        "deviceTrusted": True,
        "location": "上海",
    },
    {
        "transactionId": "TX-1043",
        "createdAt": "2026-10-28T11:00:00Z",
        "amount": 2_400_00,
        "currency": "COSMIC_COINS",
        "fromAccountId": "payroll",
        "toAccountId": DEBTOR,
        "status": "POSTED",
        "description": None,
        "beneficiaryName": "Acme Corp",
        "channel": "API",
        "deviceTrusted": True,
        "location": None,
    },
]

# The exact body keys the demo's CreateTransactionRequest accepts.
_ALLOWED_BODY_KEYS = {
    "fromAccountId",
    "toAccountId",
    "amount",
    "currency",
    "description",
    "beneficiaryName",
    "channel",
    "deviceTrusted",
    "location",
}
_REQUIRED_BODY_KEYS = {"fromAccountId", "toAccountId", "amount", "currency"}


def _demo_transport(*, recorded=None, fail_with=None, api_key="1234"):
    """Replay the demo's routing table and request validation in-process."""

    def _bad_request(message: str) -> httpx.Response:
        # The demo's Error schema is {error: {name, message}} — not a bare string.
        return httpx.Response(
            400, json={"error": {"name": "BadRequest", "message": message}}
        )

    async def handler(request: httpx.Request) -> httpx.Response:
        if recorded is not None:
            recorded.append((request.method, request.url.path))
        if fail_with is not None:
            raise fail_with(f"simulated transport failure for {request.url.path}")
        if api_key is not None and request.headers.get("x-api-key") != api_key:
            return httpx.Response(
                401, json={"error": {"name": "Unauthorized", "message": "invalid api key"}}
            )

        path = request.url.path
        if path == "/api/v1/accounts":
            return httpx.Response(200, json={"accounts": _DEMO_ACCOUNTS, "page": {}})
        if path == "/api/v1/transactions" and request.method == "GET":
            return httpx.Response(200, json={"transactions": _DEMO_TRANSACTIONS, "page": {}})
        if path == "/api/v1/transactions" and request.method == "POST":
            body = json.loads(request.content)
            # additionalProperties: false + required fields, like the real server.
            extra = set(body) - _ALLOWED_BODY_KEYS
            if extra:
                return _bad_request(f"additional properties: {sorted(extra)}")
            missing = _REQUIRED_BODY_KEYS - set(body)
            if missing:
                return _bad_request(f"missing: {sorted(missing)}")
            if not isinstance(body["amount"], int) or body["amount"] < 1:
                return _bad_request("amount must be a positive integer")
            if body["currency"] not in {"COSMIC_COINS", "GALAXY_GOLD", "MOON_BUCKS"}:
                return _bad_request("currency not in enum")
            if body["toAccountId"] not in {a["accountId"] for a in _DEMO_ACCOUNTS}:
                return _bad_request("unknown toAccountId")
            posted = {
                "transactionId": "TX-NEW-1",
                "createdAt": "2026-11-01T10:00:00Z",
                "amount": body["amount"],
                "currency": body["currency"],
                "fromAccountId": body["fromAccountId"],
                "toAccountId": body["toAccountId"],
                "status": "POSTED",
                "description": body.get("description"),
                "beneficiaryName": None,
                "channel": "API",
                "deviceTrusted": True,
                "location": None,
            }
            return httpx.Response(201, json={"transaction": posted})
        return httpx.Response(
            404, json={"error": {"name": "NotFound", "message": f"no route for {path}"}}
        )

    return httpx.MockTransport(handler)


@pytest.fixture
async def client():
    c = PostmanBankClient(transport=_demo_transport())
    yield c
    await c.aclose()


@pytest.fixture
async def backend():
    b = PostmanBankBackend(client=PostmanBankClient(transport=_demo_transport()))
    yield b
    await b.aclose()


# -- the three functions named by the integration brief ----------------------


async def test_get_accounts_returns_non_empty_tool_result(client):
    result = await client.get_accounts()
    assert isinstance(result, ToolResult)
    assert result.status == "ok"
    assert result.data, "the demo must return at least one account"
    assert len(result.data["accounts"]) == 3


async def test_get_transactions_returns_rows(client):
    result = await client.get_transactions()
    assert result.status == "ok"
    assert result.data["transactions"][0]["transactionId"] == "TX-1042"


async def test_execute_transfer_sends_the_demos_required_body():
    recorded_requests = []

    async def spy(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(201, json={"transaction": {"transactionId": "TX-NEW-1"}})

    client = PostmanBankClient(transport=httpx.MockTransport(spy))
    try:
        result = await client.execute_transfer(
            250.0, RECIPIENT, currency="COSMIC_COINS", from_account=DEBTOR
        )
    finally:
        await client.aclose()

    assert result.status == "ok"
    sent = recorded_requests[0]
    assert sent.headers.get("x-api-key") == "1234"
    assert sent.url.path == "/api/v1/transactions"
    body = json.loads(sent.content)
    assert set(body) == _REQUIRED_BODY_KEYS
    assert body["fromAccountId"] == DEBTOR
    assert body["toAccountId"] == RECIPIENT
    # Major unit in, minor unit on the wire.
    assert body["amount"] == 25000
    assert isinstance(body["amount"], int)


def test_minor_unit_conversion_is_round_tripped():
    assert to_minor_units(126.4) == 12640
    assert to_minor_units(0.01) == 1
    assert from_minor_units(12640) == 126.4
    assert from_minor_units(2_400_00) == 2400.0


# -- failsafe (spec section 3) ----------------------------------------------


async def test_connect_error_degrades_gracefully_with_friendly_message():
    client = PostmanBankClient(transport=_demo_transport(fail_with=httpx.ConnectError))
    result = await client.get_accounts()

    assert result.status == "error"
    assert result.message == DEMO_UNAVAILABLE_MESSAGE
    # An empty list here would look like "customer has no accounts" to the agent.
    assert result.data is None


async def test_timeout_is_reported_separately_from_downtime():
    client = PostmanBankClient(transport=_demo_transport(fail_with=httpx.TimeoutException))
    result = await client.get_transactions()
    assert result.status == "error"
    assert "did not respond" in result.message
    assert result.message != DEMO_UNAVAILABLE_MESSAGE


async def test_wrong_api_key_is_not_reported_as_service_down():
    client = PostmanBankClient(transport=_demo_transport(api_key="admin-demo-key"))
    result = await client.get_accounts()
    assert result.status == "error"
    assert "401" in result.message
    assert result.message != DEMO_UNAVAILABLE_MESSAGE


async def test_rejected_body_surfaces_the_demos_error():
    client = PostmanBankClient(transport=_demo_transport())
    # No fromAccountId -> the real server 400s; we must report that, not swallow it.
    result = await client.execute_transfer(10.0, RECIPIENT, currency="COSMIC_COINS")
    assert result.status == "error"
    assert "400" in result.message


# -- the bank2ai surface behind the gate ------------------------------------


async def test_bank2ai_accounts_map_to_the_standard_model(backend):
    from bank2ai import AccountList

    result = await backend.get_accounts()
    assert isinstance(result, AccountList)
    debtor = result.items[0]
    assert debtor.id == DEBTOR
    # bank2ai validates currency against ^[A-Z]{3}$, so the demo's token names are
    # shown as a 3-letter display code. The wire value (COSMIC_COINS) lives only
    # in the API body, never in the agent-facing model.
    assert debtor.currency == "COS"
    # minor units on the wire -> major units for the agent and the tiers
    assert debtor.availableBalance == 128450.0


async def test_transactions_are_signed_by_direction(backend):
    """The demo stores unsigned amounts; bank2ai expects expenses negative."""
    txns = await backend.get_transactions()
    by_id = {t.id: t for t in txns.items}
    assert by_id["TX-1042"].amount == -68.0  # we are the fromAccountId
    assert by_id["TX-1043"].amount == 2400.0  # we are the toAccountId
    assert by_id["TX-1042"].accountId == DEBTOR


async def test_prepare_then_execute_completes_the_two_phase_flow(backend):
    prepared = await backend.prepare_transfer(
        debtor_account_id=DEBTOR,
        creditor=CREDITOR,
        amount=250.0,
        currency="COSMIC_COINS",
        rail="domestic-IS",
    )
    assert prepared.item is not None, prepared.content
    intent_id = prepared.item.transferIntentId

    executed = await backend.execute_transfer(transfer_intent_id=intent_id)
    assert executed.item is not None, executed.content
    assert executed.item.transactionId == "TX-NEW-1"
    assert executed.item.status.value == "Settled"


async def test_prepare_refuses_a_currency_the_sandbox_does_not_offer(backend):
    """CNY is not in the demo's enum; refusing beats silently aliasing units."""
    prepared = await backend.prepare_transfer(
        debtor_account_id=DEBTOR,
        creditor=CREDITOR,
        amount=250.0,
        currency="CNY",
        rail="domestic-IS",
    )
    assert prepared.code == "currency_mismatch"
    assert "POSTMAN_DEMO_ALLOW_CURRENCY_ALIAS" in prepared.content


async def test_prepare_resolves_a_cny_amount_when_aliasing_is_opted_in(monkeypatch):
    monkeypatch.setenv("POSTMAN_DEMO_ALLOW_CURRENCY_ALIAS", "1")
    from banking_agent.config import get_postman_settings

    assert get_postman_settings().allow_currency_alias is True

    backend = PostmanBankBackend(client=PostmanBankClient(transport=_demo_transport()))
    try:
        prepared = await backend.prepare_transfer(
            debtor_account_id=DEBTOR,
            creditor=CREDITOR,
            amount=250.0,
            currency="CNY",
            rail="domestic-IS",
        )
        assert prepared.item is not None, prepared.content
        executed = await backend.execute_transfer(
            transfer_intent_id=prepared.item.transferIntentId
        )
        assert executed.item is not None, executed.content
        # Settlement happened in the account's own unit, not the caller's label.
        assert "COSMIC_COINS" in executed.content
    finally:
        await backend.aclose()


async def test_prepare_accepts_the_party_model_mcp_actually_delivers(backend):
    """Regression: over the wire `creditor` is a Party, not a dict.

    The first gated POSTMAN_DEMO run died inside the upstream with
    `'Party' object has no attribute 'get'`, because the unit tests only ever
    passed the dict form. Both shapes must work — okgate surfaces an upstream
    exception as an opaque UPSTREAM_ERROR, which is the worst thing to discover
    in front of a judge.
    """
    from bank2ai import Party

    prepared = await backend.prepare_transfer(
        debtor_account_id=DEBTOR,
        creditor=Party.model_validate(CREDITOR),
        amount=250.0,
        currency="COSMIC_COINS",
        rail="domestic-IS",
    )
    assert prepared.item is not None, prepared.content

    executed = await backend.execute_transfer(
        transfer_intent_id=prepared.item.transferIntentId
    )
    assert executed.item is not None, executed.content


async def test_prepare_rejects_a_recipient_the_sandbox_cannot_pay(backend):
    creditor = {
        "name": "外部收款人",
        "accountIdentifier": {
            "type": "accountNumber",
            "accountNumber": "acct-does-not-exist",
            "country": "CN",
        },
    }
    prepared = await backend.prepare_transfer(
        debtor_account_id=DEBTOR,
        creditor=creditor,
        amount=50.0,
        currency="COSMIC_COINS",
        rail="domestic-IS",
    )
    assert prepared.code == "unknown_recipient"


async def test_execute_rejects_an_unknown_intent(backend):
    executed = await backend.execute_transfer(transfer_intent_id="intent_never_minted")
    assert executed.code == "intent_not_found"


async def test_prepare_prices_without_moving_money(backend):
    """Security invariant: only `prepare-transfer` is spend-classified.

    okgate.yaml charges the daily ¥5,000 cap and drives the ¥1,000 Yellow / Red
    tier from this call's `amount` argument, and `execute-transfer` is explicitly
    "not priceable from their arguments". If prepare touched the write endpoint,
    the amount would be committed before the gate ever saw a price — so this test
    is the regression guard for that ordering.
    """
    hits: list[tuple[str, str]] = []
    backend.client = PostmanBankClient(transport=_demo_transport(recorded=hits))

    await backend.prepare_transfer(
        debtor_account_id=DEBTOR,
        creditor=CREDITOR,
        amount=600.0,
        currency="COSMIC_COINS",
        rail="domestic-IS",
    )
    assert ("POST", "/api/v1/transactions") not in hits
    assert any(p == "/api/v1/accounts" for _, p in hits)


async def test_unreachable_demo_raises_instead_of_returning_empty(backend):
    """Reads must not silently look like an empty account set.

    Returning `AccountList(items=[])` would let the agent conclude the customer
    is broke; the gate needs to see a transport failure and fail closed.
    """
    backend.client = PostmanBankClient(transport=_demo_transport(fail_with=httpx.ConnectError))
    with pytest.raises(BankUnavailableError):
        await backend.get_accounts()


async def test_unsupported_reads_fall_back_to_the_ledger(backend):
    """Categories/recipients are not modelled by the demo.

    The MCP tool surface must not lose tools when the backend changes, otherwise
    okgate's `get-*` read class and the frontend's account picker both change
    shape between demo modes.
    """
    categories = await backend.get_categories()
    assert categories.items


# -- opt-in: the real Postman demo ------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("POSTMAN_DEMO_LIVE"),
    reason="set POSTMAN_DEMO_LIVE=1 with the demo running (npm run dev:api, port 3000)",
)
async def test_live_demo_returns_accounts():
    client = PostmanBankClient()
    try:
        result = await client.get_accounts()
        assert result.status == "ok", f"{result.message} / {result.detail}"
        assert result.data, "live demo returned no accounts"
        assert result.data["accounts"][0]["currency"] in {
            "COSMIC_COINS",
            "GALAXY_GOLD",
            "MOON_BUCKS",
        }
    finally:
        await client.aclose()
