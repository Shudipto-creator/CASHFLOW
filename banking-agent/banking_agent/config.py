"""Runtime configuration for the bank upstream (the thing behind okgate).

Why this module exists separately from ``app/config.py``: the banking package is
a standalone, import-light layer that okgate launches as its own process
(``python -m banking_agent.bank.server``). It must be configurable through the
environment only, because ``okgate.yaml`` is a human-owned trust boundary and we
do not want to edit it every time we swap the bank behind the gate.

Zero-Trust note: switching ``upstream_mode`` changes *where data comes from*,
never *what is enforced*. Tier classification, MFA, caps, the loop breaker and
the kill switch all live in ``gate/`` and ``okgate.yaml``, both of which stay
byte-for-byte identical across ``MOCK`` and ``POSTMAN_DEMO``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

#: Operator-owned KEY=VALUE file that can set the same keys as the env vars.
#:
#: Why a file at all: okgate spawns the bank upstream with the MCP SDK's default
#: environment plus only the keys declared in okgate.yaml's `upstreams[].env`
#: (verified in @agentwares/agentguard's dist: `env: {...getDefaultEnvironment(),
#: ...upstream.env}`). An exported BANK_UPSTREAM_MODE therefore never reaches the
#: gated upstream, and okgate.yaml is a human-owned trust boundary the brief says
#: not to edit. This file is the equivalent knob on our side of that boundary.
#:
#: It selects *which bank implementation answers*, nothing more: classify, caps,
#: tiers, MFA, the loop breaker and the kill switch are read from okgate.yaml and
#: gate/tiers.py regardless of what is in here.
UPSTREAM_ENV_FILE = Path(__file__).resolve().parents[1] / "bank_upstream.env"


def _file_overrides() -> dict[str, str]:
    """Parse the operator file. Missing or unreadable means 'no overrides'."""
    try:
        lines = UPSTREAM_ENV_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    values: dict[str, str] = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _get(name: str, overrides: Optional[dict[str, str]] = None) -> Optional[str]:
    """Env first, operator file second, so a shell override always wins."""
    value = os.environ.get(name)
    if value not in (None, ""):
        return value
    if overrides is None:
        overrides = _file_overrides()
    from_file = overrides.get(name)
    return from_file if from_file not in (None, "") else None


class BankUpstreamMode(str, Enum):
    """Which implementation answers the bank2ai tools inside the gate."""

    MOCK = "mock"
    POSTMAN_DEMO = "postman_demo"


# NOTE: distinct from ``BANKING_BACKEND_MODE`` (values ``real`` / ``mock``), which
# app/routers/banking.py uses to decide whether the *gate* is opened at all.
# This one only chooses the bank implementation the gate fronts.
UPSTREAM_MODE_ENV = "BANK_UPSTREAM_MODE"

_DEFAULTS = {
    # The Postman Banking-API-Demo banking service.
    "base_url": "http://localhost:3000",
    # Verified against the demo's server.js: its routers are mounted under
    # /api/v1, so the bare paths in the brief (/accounts, /transactions) 404.
    "api_prefix": "/api/v1",
    # Demo default customer key; admin is 'admin-demo-key' (src/database/db.js).
    "api_key": "1234",
    "timeout_s": 10.0,
    # Verified against openapi/openapi.yaml: the demo has NO transfers route. A
    # money movement is `POST /api/v1/transactions` ("Post an atomic transfer or
    # deposit"), so the write path defaults there, not to /transfers.
    "transfer_path": "/api/v1/transactions",
    # The demo's only currencies are COSMIC_COINS / GALAXY_GOLD / MOON_BUCKS and
    # every monetary field is a non-negative integer in MINOR UNITS. There is no
    # CNY in the sandbox, so amounts must be converted at this boundary — see the
    # unit invariant in bank/postman_adapter.py.
    "currency": "COSMIC_COINS",
    # Optional demo run isolation header (X-Demo-Run-Id); unset uses the demo's
    # DEFAULT_RUN_ID.
    "run_id": None,
}


@dataclass(frozen=True)
class PostmanDemoSettings:
    """Connection settings for the Postman Banking-API-Demo."""

    base_url: str
    api_prefix: str
    api_key: str
    timeout_s: float
    transfer_path: str
    currency: str
    run_id: Optional[str]
    allow_currency_alias: bool

    @property
    def accounts_url(self) -> str:
        return f"{self.base_url}{self.api_prefix}/accounts"

    @property
    def transactions_url(self) -> str:
        return f"{self.base_url}{self.api_prefix}/transactions"

    @property
    def transfer_url(self) -> str:
        return f"{self.base_url}{self.transfer_path}"


@dataclass(frozen=True)
class BankUpstreamSettings:
    mode: BankUpstreamMode
    postman: PostmanDemoSettings

    def describe(self) -> str:
        if self.mode is BankUpstreamMode.POSTMAN_DEMO:
            return f"POSTMAN_DEMO -> {self.postman.base_url} (prefix {self.postman.api_prefix})"
        return "MOCK -> in-memory bank2ai ledger"


def _env(name: str, fallback: str, overrides: dict[str, str]) -> str:
    return _get(name, overrides) or fallback


def _env_float(name: str, fallback: float, overrides: dict[str, str]) -> float:
    try:
        return float(_env(name, str(fallback), overrides))
    except ValueError:
        return fallback


def _env_bool(name: str, fallback: bool, overrides: dict[str, str]) -> bool:
    value = _get(name, overrides)
    if value is None:
        return fallback
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_postman_settings(
    overrides: Optional[dict[str, str]] = None,
) -> PostmanDemoSettings:
    """Read Postman demo connection settings (env, then the operator file).

    ``POSTMAN_DEMO_TRANSFER_PATH`` defaults to the transactions endpoint because
    that is where the demo commits money; override it if your fork moves it.
    ``POSTMAN_DEMO_CURRENCY`` must be one of the demo's three enum values, since
    the schema rejects anything else.
    """
    overrides = _file_overrides() if overrides is None else overrides
    prefix = _env("POSTMAN_DEMO_API_PREFIX", _DEFAULTS["api_prefix"], overrides).rstrip("/")
    prefix = prefix or "/api/v1"
    return PostmanDemoSettings(
        base_url=_env("POSTMAN_DEMO_BASE_URL", _DEFAULTS["base_url"], overrides).rstrip("/"),
        api_prefix=prefix,
        api_key=_env("POSTMAN_DEMO_API_KEY", _DEFAULTS["api_key"], overrides),
        timeout_s=_env_float("POSTMAN_DEMO_TIMEOUT_S", _DEFAULTS["timeout_s"], overrides),
        transfer_path=_env(
            "POSTMAN_DEMO_TRANSFER_PATH",
            _env("POSTMAN_DEMO_TRANSACTIONS_PATH", f"{prefix}/transactions", overrides),
            overrides,
        ),
        currency=_env("POSTMAN_DEMO_CURRENCY", _DEFAULTS["currency"], overrides),
        run_id=_get("POSTMAN_DEMO_RUN_ID", overrides),
        # The sandbox only speaks COSMIC_COINS/GALAXY_GOLD/MOON_BUCKS, while the
        # agent and the ¥ thresholds are written in CNY. Off by default: silently
        # treating "CNY" as sandbox tokens would make the ¥1,000 / ¥5,000 tiers
        # count a unit the bank never charged, which is the failure mode
        # okgate.yaml's CURRENCY comment warns about. Turn it on explicitly for a
        # functional (not monetary-accurate) demo run.
        allow_currency_alias=_env_bool(
            "POSTMAN_DEMO_ALLOW_CURRENCY_ALIAS", False, overrides
        ),
    )


def get_bank_upstream_settings() -> BankUpstreamSettings:
    """Resolve the upstream mode. Unrecognised values fail closed to MOCK."""
    overrides = _file_overrides()
    raw = _get(UPSTREAM_MODE_ENV, overrides) or BankUpstreamMode.MOCK.value
    try:
        mode = BankUpstreamMode(raw.strip().lower())
    except ValueError:
        mode = BankUpstreamMode.MOCK
    return BankUpstreamSettings(mode=mode, postman=get_postman_settings(overrides))
