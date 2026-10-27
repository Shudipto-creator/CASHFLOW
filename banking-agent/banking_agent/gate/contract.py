"""The interface contract between the security gate and its callers.

Everything the UI, the agent loop, and the tests need to branch on lives here:
the tier enum, the error codes, and the two result types. Nothing in this
module talks to okgate or the bank — it is pure vocabulary.

Error codes come from two sources and callers must be able to tell them apart:

* **okgate** (``OKGATE_CODES``) — emitted by the policy proxy. Treat these as
  authoritative security refusals: never retry them without changing something
  a human controls.
* **this layer** (``MFA_*``, ``CONFIRMATION_*``) — okgate has no MFA, so Red-tier
  strong verification is implemented here, before any tool call leaves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Optional


class Tier(str, Enum):
    """Track 2 §III.1 access-control levels."""

    GREEN = "green"
    """Automatic execution. Read-only operations: balances, history, analysis."""

    YELLOW = "yellow"
    """User confirmation. Transfers whose daily cumulative total is ¥1,000 or less."""

    RED = "red"
    """Strong verification (MFA). Transfers pushing the daily cumulative over ¥1,000."""


#: Track 2 §III.1: Yellow is "¥1,000 or less", Red is "over ¥1,000".
#: The comparison is on the *projected* daily total — everything already
#: committed today **plus** this operation — not on the single amount.
YELLOW_DAILY_CEILING_CNY = Decimal("1000")


class GateCode(str, Enum):
    """Every refusal a caller must handle."""

    # --- emitted by okgate -------------------------------------------------
    KILLED = "KILLED"
    TOOL_DENIED = "TOOL_DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    LOOP_DETECTED = "LOOP_DETECTED"
    CAP_EXCEEDED = "CAP_EXCEEDED"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"

    # --- emitted by this layer, because okgate has no MFA ------------------
    MFA_REQUIRED = "MFA_REQUIRED"
    MFA_FAILED = "MFA_FAILED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"

    # --- emitted by the mock bank ------------------------------------------
    INSUFFICIENT_FUNDS = "insufficient_funds"
    INVALID_ACCOUNT = "invalid_account"
    CURRENCY_MISMATCH = "currency_mismatch"
    INTENT_NOT_FOUND = "intent_not_found"
    INTENT_EXPIRED = "intent_expired"
    INTENT_ALREADY_EXECUTED = "intent_already_executed"


#: Codes that prove the policy proxy refused the call.
OKGATE_CODES = frozenset(
    {
        GateCode.KILLED,
        GateCode.TOOL_DENIED,
        GateCode.APPROVAL_REQUIRED,
        GateCode.LOOP_DETECTED,
        GateCode.CAP_EXCEEDED,
    }
)


@dataclass(frozen=True)
class TieredCall:
    """The tier decision for one prospective operation, with its reasoning."""

    tool: str
    tier: Tier
    reason: str
    amount_cny: Optional[Decimal] = None
    projected_daily_cny: Optional[Decimal] = None

    @property
    def needs_confirmation(self) -> bool:
        """Yellow and Red both need a human; only Green is automatic."""
        return self.tier is not Tier.GREEN

    @property
    def needs_mfa(self) -> bool:
        return self.tier is Tier.RED


@dataclass
class GateResult:
    """One tool call's raw outcome as it came back through the okgate proxy."""

    tool: str
    ok: bool
    code: Optional[str] = None
    message: str = ""
    value: Optional[dict[str, Any]] = None
    details: Optional[dict[str, Any]] = None

    @property
    def refused_by_gate(self) -> bool:
        return not self.ok and self.code in OKGATE_CODES


@dataclass
class GateOutcome:
    """What a caller of :class:`SecureBankGate` always gets back.

    A single type for every path — tier refusals produced locally, okgate
    refusals, and bank business errors — so the UI has exactly one shape to
    render.
    """

    ok: bool
    message: str = ""
    code: Optional[str] = None
    tier: Optional[Tier] = None
    amount_cny: Optional[Decimal] = None
    projected_daily_cny: Optional[Decimal] = None
    transfer_intent_id: Optional[str] = None
    approval_id: Optional[str] = None
    approval_command: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)
    result: Optional[GateResult] = None

    @property
    def value(self) -> Optional[dict[str, Any]]:
        """The bank's response payload, when the call produced one."""
        return self.result.value if self.result else None

    @classmethod
    def from_result(cls, result: GateResult, **extra: Any) -> "GateOutcome":
        return cls(
            ok=result.ok,
            message=result.message,
            code=result.code,
            details=result.details or {},
            result=result,
            **extra,
        )
