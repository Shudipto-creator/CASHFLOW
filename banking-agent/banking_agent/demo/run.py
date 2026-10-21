"""Scenario runs against the live stack: mock bank -> okgate -> SecureBankGate.

Each scenario resets the gate's state first, so any one of them can be run on
its own and the numbers in the output are always the same. That matters more
than it sounds: okgate's caps and the ¥1,000 tier ceiling are both *cumulative*,
so a demo that inherited yesterday's counters would tell a different story on
every machine.

Every scenario ends in `check(...)` calls rather than printed prose, so the
same file doubles as the end-to-end test and its exit code is meaningful.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Coroutine

from ..gate import (
    DailySpendLedger,
    GateClient,
    GateCode,
    SecureBankGate,
    SmsCodeMfa,
    Tier,
    TransferOutcome,
)

#: banking-agent/ — the directory that holds okgate.yaml.
ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "okgate.yaml"
STATE = ROOT / ".state"
SPEND_LEDGER = STATE / "daily_spend.json"

DEBTOR = "acc_cmb_001"

#: A recipient from the mock bank's seed data. `accountNumber` is the right
#: identifier for a Chinese market: the country carries an ISO 3166 code and
#: the number itself is free format.
CREDITOR: dict[str, Any] = {
    "name": "李娜",
    "accountIdentifier": {
        "type": "accountNumber",
        "accountNumber": "6225 8888 0000 1234",
        "country": "CN",
    },
}

#: One-time codes the verifier "delivered", keyed by challenge id. Stands in
#: for the phone the real code would reach; the demo reads it from here
#: because there is no phone in a terminal.
DELIVERED: dict[str, str] = {}

RESULTS: list[tuple[bool, str]] = []


# --- reporting ------------------------------------------------------------


def section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def check(label: str, passed: Any, detail: str = "") -> bool:
    passed = bool(passed)
    RESULTS.append((passed, label))
    line = f"  [{'PASS' if passed else 'FAIL'}] {label}"
    if detail:
        line += f"  — {detail}"
    print(line)
    return passed


# --- wiring ---------------------------------------------------------------


def reset_state() -> None:
    """Clear okgate's counters, the audit log, and the daily spend total."""
    for path in (ROOT / ".okgate", STATE):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def _deliver(subject: str, challenge_id: str, code: str) -> None:
    DELIVERED[challenge_id] = code
    print(f"    [SMS to {subject}] verification code {code} (challenge {challenge_id})")


def build_gate(client: GateClient) -> SecureBankGate:
    DELIVERED.clear()
    return SecureBankGate(
        client=client,
        spend=DailySpendLedger(SPEND_LEDGER),
        mfa=SmsCodeMfa(deliver=_deliver),
        subject="张小伟",
    )


async def prepare(gate: SecureBankGate, amount: float, **extra: Any) -> TransferOutcome:
    """A transfer the user has already approved in the UI.

    `confirmed=True` answers the Yellow prompt; a Red amount still needs an
    MFA round trip on top, which is why the returned outcome has to be read
    rather than assumed.
    """
    return await gate.transfer(
        debtor_account_id=DEBTOR,
        creditor=CREDITOR,
        amount=amount,
        confirmed=True,
        **extra,
    )


def code_of(outcome: TransferOutcome, phase: str = "prepared") -> str:
    step = getattr(outcome, phase)
    return (step.code if step else None) or "ok"


# --- scenarios ------------------------------------------------------------


async def scenario_green(gate: SecureBankGate, client: GateClient) -> None:
    section("GREEN — read-only operations run with no human in the loop")

    accounts = await gate.call("get-accounts", {})
    check("get-accounts passed the gate and executed", accounts.ok, accounts.message)
    check("it was classified GREEN", accounts.tier is Tier.GREEN)
    check("no confirmation was demanded of the user", accounts.code is None)

    items = (accounts.value or {}).get("items") or []
    check("the bank returned all three seeded accounts", len(items) == 3, f"{len(items)} accounts")

    summary = await gate.call(
        "get-transactions-summary", {"direction": "Expenses", "group_by": "category"}
    )
    check("a second read (spend by category) also ran automatically", summary.ok, summary.message)


async def scenario_yellow(gate: SecureBankGate, client: GateClient) -> None:
    section("YELLOW — a ¥600 transfer waits for the user's confirmation")

    first = await gate.transfer(debtor_account_id=DEBTOR, creditor=CREDITOR, amount=600)
    check(
        "the unconfirmed attempt was held, not sent",
        code_of(first) == GateCode.CONFIRMATION_REQUIRED.value,
        first.message,
    )
    check("it was classified YELLOW", first.tier is Tier.YELLOW)

    second = await prepare(gate, 600)
    check("confirming released the intent", second.ok, second.message)
    check("the bank issued a transfer intent id", bool(second.intent_id), str(second.intent_id))
    check(
        "today's authorised total is ¥600",
        gate.spent_today() == Decimal("600"),
        f"¥{gate.spent_today()}",
    )
    check(
        "the intent is a hold only — the balance is untouched",
        not (second.prepared.result.value or {}).get("item", {}).get("transactionId"),
    )


async def scenario_red(gate: SecureBankGate, client: GateClient) -> None:
    section("RED — the tier follows the daily total, not the single amount")

    await prepare(gate, 600)
    print(f"    ¥600 already authorised today, so ¥500 projects to ¥1,100")

    first = await gate.transfer(debtor_account_id=DEBTOR, creditor=CREDITOR, amount=500)
    check(
        "¥500 was classified RED even though it is a small amount",
        first.tier is Tier.RED,
        "the cumulative daily total is what the spec keys on",
    )
    check(
        "a strong-verification challenge was issued",
        code_of(first) == GateCode.MFA_REQUIRED.value,
        first.message,
    )

    challenge = (first.prepared.details or {}).get("challenge_id")
    check("the challenge has an id and the code left out of band", bool(challenge), str(challenge))

    wrong = await prepare(gate, 500, mfa_challenge_id=challenge, mfa_code="000000")
    check(
        "a wrong code is refused and the call is never sent",
        code_of(wrong) == GateCode.MFA_FAILED.value,
        wrong.message,
    )

    right = await prepare(
        gate, 500, mfa_challenge_id=challenge, mfa_code=DELIVERED.get(challenge, "")
    )
    check("the correct code released the transfer", right.ok, right.message)
    check(
        "today's total is now ¥1,100",
        gate.spent_today() == Decimal("1100"),
        f"¥{gate.spent_today()}",
    )

    replay = await prepare(
        gate, 500, mfa_challenge_id=challenge, mfa_code=DELIVERED.get(challenge, "")
    )
    check(
        "the same code cannot be replayed",
        code_of(replay) == GateCode.MFA_FAILED.value,
        "a verified challenge is consumed",
    )


async def scenario_approval(gate: SecureBankGate, client: GateClient) -> None:
    section("APPROVAL — okgate holds the money movement until a human releases it")

    prepared = await prepare(gate, 600)
    check("the intent was prepared under the Yellow rule", prepared.ok, prepared.message)
    intent = prepared.intent_id or ""

    held = await gate.execute(intent)
    check(
        "execute-transfer was held by the policy proxy",
        code_of(held, "executed") == GateCode.APPROVAL_REQUIRED.value,
        held.message,
    )
    check("the refusal names the approval that is pending", bool(held.approval_id), str(held.approval_id))
    check("the refusal came from the gate, not the bank", bool(held.executed.result.refused_by_gate))
    print(f"    a human releases it with: {held.executed.approval_command}")

    released = await client.approve(held.approval_id or "")
    print(f"    okgate approve -> {released}")

    settled = await gate.execute(intent)
    check("after approval the transfer settled", settled.ok, settled.message)
    tx = ((settled.executed.value or {}).get("item") or {}).get("transactionId")
    check("the bank reported a settled transaction", bool(tx), str(tx))

    again = await gate.execute(intent)
    check(
        "replaying the same intent did not move money again",
        not again.ok,
        f"caught by {code_of(again, 'executed')}",
    )


async def scenario_cap(gate: SecureBankGate, client: GateClient) -> None:
    section("CAP — the hard ceiling wins even after strong verification")

    first = await gate.transfer(debtor_account_id=DEBTOR, creditor=CREDITOR, amount=6000)
    check("¥6,000 is classified RED", first.tier is Tier.RED)

    challenge = (first.prepared.details or {}).get("challenge_id")
    result = await prepare(
        gate, 6000, mfa_challenge_id=challenge, mfa_code=DELIVERED.get(challenge, "")
    )
    check(
        "the user verified, and okgate still refused the call",
        code_of(result) == GateCode.CAP_EXCEEDED.value,
        result.message,
    )
    check(
        "nothing moved and nothing was charged",
        gate.spent_today() == Decimal("0"),
        f"¥{gate.spent_today()}",
    )


async def scenario_loop(gate: SecureBankGate, client: GateClient) -> None:
    section("LOOP — a stuck agent repeating itself is cut off")

    codes: list[str] = []
    for attempt in range(1, 8):
        outcome = await prepare(gate, 10)
        codes.append(code_of(outcome))
        print(f"    identical prepare-transfer #{attempt}: {codes[-1]}")

    tripped = next(
        (i for i, code in enumerate(codes) if code == GateCode.LOOP_DETECTED.value), None
    )
    check("the first two identical calls were allowed", codes[0] == "ok" and codes[1] == "ok")
    check(
        "the breaker tripped inside the window",
        tripped is not None,
        f"first refusal on repeat #{tripped + 1}" if tripped is not None else "never tripped",
    )
    check(
        "every repeat after that is refused as well",
        tripped is not None and all(c == GateCode.LOOP_DETECTED.value for c in codes[tripped:]),
    )


async def scenario_kill(gate: SecureBankGate, client: GateClient) -> None:
    section("KILL SWITCH — one file stops every call, reads included")

    switch = client.state_dir / "KILL"
    switch.parent.mkdir(parents=True, exist_ok=True)
    switch.write_text("operator pressed the kill switch", encoding="utf-8")
    try:
        read = await gate.call("get-accounts", {})
        check(
            "a read-only call was refused while the switch is on",
            read.code == GateCode.KILLED.value,
            read.message,
        )
        spend = await prepare(gate, 100)
        check("a spend was refused as well", code_of(spend) == GateCode.KILLED.value, spend.message)
    finally:
        switch.unlink(missing_ok=True)

    await client.resume()
    after = await gate.call("get-accounts", {})
    check("clearing the switch resumes normal service", after.ok, after.message)


async def scenario_audit(gate: SecureBankGate, client: GateClient) -> None:
    section("AUDIT — a hash-chained trail of every gated call")

    await gate.call("get-accounts", {})
    await prepare(gate, 200)
    for _ in range(3):
        await prepare(gate, 10)  # an identical repeat, so okgate refuses one of them
    await gate.call("get-transactions", {"count": 3})

    entries = await client.read_audit()
    check("every gated call left an entry", len(entries) >= 3, f"{len(entries)} entries")
    check(
        "okgate's own refusals are recorded too",
        any((e.get("error") or {}).get("code") for e in entries),
    )

    print(f"    {'seq':>3}  {'tool':<24}{'class':<8}{'outcome':<10}{'usd':>6}  code")
    for entry in entries:
        error = entry.get("error") or {}
        usd = entry.get("usd")
        print(
            f"    {entry.get('seq', 0):>3}  {entry.get('tool', ''):<24}"
            f"{entry.get('class', ''):<8}{entry.get('outcome', ''):<10}"
            f"{(f'{usd:g}' if isinstance(usd, (int, float)) else '-'):>6}  "
            f"{error.get('code', '')}"
        )

    good = await client.verify_audit()
    check("okgate verified the chain", "intact" in good.lower(), _last_line(good))

    tampered = STATE / "audit-tampered.jsonl"
    lines = client.audit_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["tool"] = "get-transactions"  # pretend this entry was a different call
    lines[0] = json.dumps(first, ensure_ascii=False)
    tampered.parent.mkdir(parents=True, exist_ok=True)
    tampered.write_text("\n".join(lines) + "\n", encoding="utf-8")

    broken = await client.verify_audit(tampered)
    check("editing one entry breaks the chain and is reported", "broken" in broken.lower(), _last_line(broken))
    tampered.unlink(missing_ok=True)


def _last_line(text: str) -> str:
    lines = [line for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else (text or "").strip()


SCENARIOS: dict[str, Callable[..., Coroutine[Any, Any, None]]] = {
    "green": scenario_green,
    "yellow": scenario_yellow,
    "red": scenario_red,
    "approval": scenario_approval,
    "cap": scenario_cap,
    "loop": scenario_loop,
    "kill": scenario_kill,
    "audit": scenario_audit,
}

ORDER = ["green", "yellow", "red", "approval", "cap", "loop", "kill", "audit"]


async def run(names: list[str]) -> int:
    for name in names:
        reset_state()
        async with GateClient(policy=POLICY, root=ROOT, run_id=f"demo-{name}") as client:
            gate = build_gate(client)
            await SCENARIOS[name](gate, client)

    failures = [label for passed, label in RESULTS if not passed]
    print(f"\n{len(RESULTS) - len(failures)}/{len(RESULTS)} checks passed")
    for label in failures:
        print(f"  failed: {label}")
    return len(failures)


def main(argv: list[str] | None = None) -> int:
    requested = (argv if argv is not None else sys.argv[1:]) or ORDER
    unknown = [name for name in requested if name not in SCENARIOS]
    if unknown:
        print(f"unknown scenario(s): {', '.join(unknown)}")
        print(f"available: {', '.join(ORDER)}")
        return 2
    return asyncio.run(run(requested))


if __name__ == "__main__":
    raise SystemExit(main())
