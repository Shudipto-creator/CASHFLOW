"""Sandbox integration tests: bank-backend modes + AgentVault detection.

Three things the demo depends on:

1. ``POSTMAN_DEMO`` mode answers the same bank2ai tools over HTTP (httpx mocked,
   so no Node service is required in CI).
2. ``MOCK`` mode is untouched — the 41 existing gate/tier/MFA tests keep meaning
   the same thing after this integration.
3. The backend can tell whether it is running inside an AgentVault wrapper, and
   says so out loud when it is not.

Note on (3): AgentVault's ``wrap`` filters the *environment* only (verified: it
spawns with a rebuilt env and ships no firewall/namespace/proxy code), so these
tests assert credential-marker detection, not network isolation. Treating a
successful ``wrap`` as proof of network containment would be a false claim to a
security judge.
"""

from __future__ import annotations

import importlib
import logging
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from banking_agent.config import BankUpstreamMode, get_bank_upstream_settings, get_postman_settings
from banking_agent.bank import server as bank_server
from banking_agent.bank.postman_adapter import PostmanBankClient

# The FastAPI layer lives one level above this standalone package, so import it
# explicitly instead of pretending the two share a venv.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _ignore_operator_files(monkeypatch, tmp_path):
    from banking_agent import config as bank_config

    monkeypatch.setattr(bank_config, "UPSTREAM_ENV_FILE", tmp_path / "missing.env")
    monkeypatch.setattr(
        bank_config, "LOCAL_UPSTREAM_ENV_FILE", tmp_path / "missing-local.env"
    )


# -- mode flag ---------------------------------------------------------------


def test_mode_defaults_to_mock_without_operator_configuration(monkeypatch, tmp_path):
    _ignore_operator_files(monkeypatch, tmp_path)
    monkeypatch.delenv("BANK_UPSTREAM_MODE", raising=False)
    assert get_bank_upstream_settings().mode is BankUpstreamMode.MOCK


def test_mode_reads_postman_demo_from_env(monkeypatch, tmp_path):
    _ignore_operator_files(monkeypatch, tmp_path)
    monkeypatch.setenv("BANK_UPSTREAM_MODE", "postman_demo")
    monkeypatch.setenv("POSTMAN_DEMO_BASE_URL", "http://localhost:3000")
    settings = get_bank_upstream_settings()
    assert settings.mode is BankUpstreamMode.POSTMAN_DEMO
    # Verified against the demo's server.js: routers are mounted under /api/v1.
    assert settings.postman.accounts_url == "http://localhost:3000/api/v1/accounts"
    # Verified against its openapi.yaml: there is no /transfers route at all — a
    # money movement is a POST to the transactions collection.
    assert settings.postman.transfer_url == "http://localhost:3000/api/v1/transactions"


def test_unknown_mode_fails_closed_to_mock(monkeypatch):
    """A typo must not silently reach a live bank endpoint."""
    monkeypatch.setenv("BANK_UPSTREAM_MODE", "prod_bank")
    assert get_bank_upstream_settings().mode is BankUpstreamMode.MOCK


def test_operator_file_selects_the_mode(monkeypatch, tmp_path):
    """The file, not the shell, is the switch that works behind okgate.

    Verified against @agentwares/agentguard's dist: the upstream is spawned with
    `env: {...getDefaultEnvironment(), ...upstream.env}`, so an exported
    BANK_UPSTREAM_MODE cannot reach it and okgate.yaml is a trust boundary we do
    not edit per experiment. banking-agent/bank_upstream.env is the equivalent
    operator-owned knob.
    """
    from banking_agent import config as bank_config

    monkeypatch.delenv("BANK_UPSTREAM_MODE", raising=False)
    probe = tmp_path / "bank_upstream.env"
    probe.write_text("# comment\nBANK_UPSTREAM_MODE=postman_demo\n", encoding="utf-8")
    monkeypatch.setattr(bank_config, "UPSTREAM_ENV_FILE", probe)
    assert get_bank_upstream_settings().mode is BankUpstreamMode.POSTMAN_DEMO


def test_environment_beats_the_operator_file(monkeypatch, tmp_path):
    """A shell override must still win, so standalone runs stay predictable."""
    from banking_agent import config as bank_config

    probe = tmp_path / "bank_upstream.env"
    probe.write_text("BANK_UPSTREAM_MODE=postman_demo\n", encoding="utf-8")
    monkeypatch.setattr(bank_config, "UPSTREAM_ENV_FILE", probe)
    monkeypatch.setenv("BANK_UPSTREAM_MODE", "mock")
    assert get_bank_upstream_settings().mode is BankUpstreamMode.MOCK


def test_shipped_operator_file_does_not_enable_transfer_writes():
    """The tracked operator config must leave sandbox transfers read-only."""
    from banking_agent.config import UPSTREAM_ENV_FILE

    if not UPSTREAM_ENV_FILE.exists():
        pytest.skip("no operator file in this checkout")
    configured_writable = any(
        line.partition("=")[0].strip() == "POSTMAN_DEMO_READ_ONLY"
        and line.partition("=")[2].strip().lower() in {"0", "false", "no", "off"}
        for line in UPSTREAM_ENV_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#") and "=" in line
    )
    assert not configured_writable, "bank_upstream.env must not enable transfer writes"


def test_build_bank_backend_selects_by_mode(monkeypatch, tmp_path):
    _ignore_operator_files(monkeypatch, tmp_path)
    monkeypatch.delenv("BANK_UPSTREAM_MODE", raising=False)
    assert isinstance(bank_server.build_bank_backend(), bank_server.Ledger)

    monkeypatch.setenv("BANK_UPSTREAM_MODE", "postman_demo")
    from banking_agent.bank.postman_adapter import PostmanBankBackend

    assert isinstance(bank_server.build_bank_backend(), PostmanBankBackend)


async def test_tool_surface_is_identical_in_both_modes(monkeypatch):
    """Backend-agnostic proof: same tool names, either mode.

    okgate classifies by tool name (`get-*` read / `prepare-transfer` spend /
    execute-transfer + create-recipient write) and blocks anything unknown, so a
    name drift between modes would silently change which calls are
    policy-enforced. Asserted against the real registered set.
    """
    async def surface(mode_env):
        monkeypatch.setenv("BANK_UPSTREAM_MODE", mode_env)
        tools = await bank_server.build_server()._list_tools()
        return sorted(t.name for t in tools)

    expected = [
        "create-recipient",
        "execute-transfer",
        "get-accounts",
        "get-categories",
        "get-recipients",
        "get-transaction",
        "get-transactions",
        "get-transactions-summary",
        "prepare-transfer",
    ]
    mock_tools = await surface("mock")
    demo_tools = await surface("postman_demo")
    assert mock_tools == demo_tools == expected


# -- POSTMAN_DEMO: httpx mocked ----------------------------------------------


def _stub_transport(request: httpx.Request) -> httpx.Response:
    assert request.headers.get("x-api-key"), "the demo requires x-api-key"
    if request.url.path == "/api/v1/accounts":
        return httpx.Response(
            200,
            json={
                "accounts": [
                    {
                        # Row-shaped exactly as the demo serves it — its own field
                        # names, a whole-token integer balance, a token currency and
                        # an ACTIVE status. None of it is bank2ai-shaped: the
                        # adapter owns the whole mapping.
                        "accountId": "1",
                        "owner": "Nova Newman",
                        "accountType": "STANDARD",
                        "createdAt": "2026-01-04",
                        "balance": 6_150,
                        "currency": "COSMIC_COINS",
                        "status": "ACTIVE",
                    }
                ]
            },
        )
    if request.url.path == "/api/v1/transactions":
        return httpx.Response(
            200,
            json={
                "transactions": [
                    {
                        "transactionId": "TX-1042",
                        "fromAccountId": "1",
                        "toAccountId": "merchant-1",
                        "amount": 68,
                        "currency": "COSMIC_COINS",
                        "createdAt": "2026-03-01T09:00:00Z",
                        "description": "咖啡",
                    }
                ]
            },
        )
    return httpx.Response(404, json={"error": "unhandled"})


async def test_postman_mode_get_accounts_returns_a_list():
    client = PostmanBankClient(transport=httpx.MockTransport(_stub_transport))
    try:
        result = await client.get_accounts()
    finally:
        await client.aclose()
    assert result.status == "ok"
    assert isinstance(result.data["accounts"], list)
    assert result.data["accounts"]


async def test_postman_mode_answers_through_the_bank2ai_models():
    from banking_agent.bank.postman_adapter import PostmanBankBackend
    from bank2ai import AccountList

    backend = PostmanBankBackend(
        client=PostmanBankClient(
            settings=replace(get_postman_settings(), amount_scale=1),
            transport=httpx.MockTransport(_stub_transport),
        )
    )
    accounts = await backend.get_accounts()
    assert isinstance(accounts, AccountList)
    # Exponent-zero sandbox currency units are passed through to the gate.
    assert accounts.items[0].availableBalance == 6150.0
    # bank2ai requires ^[A-Z]{3}$, so the token name is shown truncated
    assert accounts.items[0].currency == "COS"

    transactions = await backend.get_transactions()
    # the demo stores unsigned amounts; bank2ai expects an outflow negative
    assert transactions.items[0].amount == -68.0


# -- MOCK: the existing bank keeps working -----------------------------------


async def test_mock_bank_still_works():
    from banking_agent.bank.ledger import Ledger

    ledger = Ledger()
    accounts = await ledger.get_accounts()
    assert accounts.items, "seeded mock accounts missing"
    transactions = await ledger.get_transactions(count=3)
    assert len(transactions.items) <= 3


async def test_mock_bank_two_phase_transfer_still_works():
    from banking_agent.bank.ledger import Ledger

    ledger = Ledger()
    prepared = await ledger.prepare_transfer(
        debtor_account_id="acc_cmb_001",
        creditor={
            "name": "李娜",
            "accountIdentifier": {
                "type": "accountNumber",
                "accountNumber": "6225 8888 0000 1234",
                "country": "CN",
            },
        },
        amount=120.0,
        currency="CNY",
        rail="domestic-IS",
    )
    assert prepared.item is not None
    executed = await ledger.execute_transfer(
        transfer_intent_id=prepared.item.transferIntentId
    )
    assert executed.item is not None and executed.item.status.value == "Settled"


# -- AgentVault detection ----------------------------------------------------


@pytest.fixture(scope="module")
def sandbox_module():
    try:
        return importlib.import_module("app.middleware.sandbox")
    except ImportError as exc:  # pragma: no cover - banking-only venv
        pytest.skip(f"FastAPI layer not importable here: {exc}")


@pytest.fixture
def clean_env(monkeypatch):
    for name in (
        "AGENTVAULT_SESSION",
        "AGENTVAULT_PROFILE",
        "AGENTVAULT_TRUST",
        "AGENTVAULT_SANDBOX_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_detect_sandbox_reports_none_when_unwrapped(sandbox_module, clean_env):
    assert sandbox_module.detect_sandbox() == {
        "active": False,
        "provider": "none",
        "profile": None,
        "trust": None,
        "session": None,
        "markers": [],
    }


def test_detect_sandbox_reads_the_vars_agentvault_actually_injects(sandbox_module, clean_env):
    """Keys asserted as they appear in buildEnv.js: SESSION, PROFILE, TRUST."""
    state = sandbox_module.detect_sandbox(
        {
            "PATH": "/usr/bin",
            "AGENTVAULT_SESSION": "sess_42",
            "AGENTVAULT_PROFILE": "restrictive",
            "AGENTVAULT_TRUST": "0",
        }
    )
    assert state["active"] is True
    assert state["provider"] == "agentvault"
    assert state["profile"] == "restrictive"
    assert state["session"] == "sess_42"


def test_agentvault_sandbox_id_alias_is_also_accepted(sandbox_module, clean_env):
    assert sandbox_module.detect_sandbox({"AGENTVAULT_SANDBOX_ID": "abc"})["active"] is True


def test_startup_logs_the_exact_failsafe_warning(sandbox_module, clean_env, caplog):
    with caplog.at_level(logging.WARNING, logger="app.middleware.sandbox"):
        sandbox_module.log_startup_sandbox_state()
    assert "Running outside AgentVault sandbox. Security isolation is not active." in caplog.text


def test_startup_logs_an_accurate_notice_when_wrapped(sandbox_module, clean_env, caplog):
    clean_env.setenv("AGENTVAULT_PROFILE", "restrictive")
    clean_env.setenv("AGENTVAULT_SESSION", "sess_42")
    clean_env.setenv("AGENTVAULT_TRUST", "0")

    with caplog.at_level(logging.INFO, logger="app.middleware.sandbox"):
        sandbox_module.log_startup_sandbox_state()

    text = caplog.text
    assert "AgentVault sandbox detected" in text
    assert "restrictive" in text
    # The warning must not fire while wrapped, and the log must not overclaim:
    assert "Security isolation is not active" not in text
    assert "does not" in text and "network isolation" in text


async def test_middleware_tags_requests_and_echoes_the_header(sandbox_module):
    """Drives the middleware directly: no app import, no bound port."""
    seen = {}

    async def call_next(request):
        seen["state"] = request.state.sandbox
        return SimpleNamespace(headers={})

    request = SimpleNamespace(state=SimpleNamespace())
    response = await sandbox_module.sandbox_inspection_middleware(request, call_next)

    assert seen["state"]["provider"] in {"none", "agentvault"}
    assert response.headers["X-Sandbox"] == seen["state"]["provider"]
