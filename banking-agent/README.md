# banking-agent — the security integration layer

Track 2 ("AI Agent for Banks") requires a hierarchical access-control mechanism,
a set of security mechanisms, and an operational audit trail. This package is the
layer that provides all three for the whole team, so that a scenario owner can
write business logic without re-implementing any of them.

Two third-party projects do the heavy lifting, and neither is vendored:

- **[bank2ai](https://github.com/bank2ai/bank2ai)** — the standardized banking
  tool adapter. `register_tools(app, get_accounts=..., execute_transfer=...)`
  exposes Python handlers as MCP tools with bank2ai's canonical names and
  schemas. The mock bank is ours; the tool surface is a standard.
- **[okgate](https://github.com/ubukhari/okgate)** (npm `@agentwares/agentguard`)
  — an MCP policy proxy. Kill switch, per-agent scope, destructive-action
  approvals, the loop breaker, hard spend caps, and a hash-chained audit log.

## Architecture

```
  scenario code / LLM host / web chat
                │
                ▼
      banking_agent.gate.SecureBankGate      tiers → MFA → confirmation
                │                                (okgate cannot express these)
                ▼
      banking_agent.gate.GateClient          one StdioTransport
                │
                │  npx -p @agentwares/agentguard okgate proxy --config okgate.yaml
                ▼
                okgate  ──  kill switch · scope · classify · approvals
                │           loop breaker · caps · audit chain
                ▼
      banking_agent.bank.server              our mock ledger, via bank2ai
                │
                ▼
      banking_agent.bank.ledger.Ledger       in-memory accounts + intents
```

**The rule that makes this worth anything:** the only route to the bank is
through okgate. `GateClient` spawns the proxy as a child process, and the proxy
spawns the bank as *its* upstream. Nothing in this repository opens a second
connection to `banking_agent.bank.server`. If any code ever does, the gate stops
meaning anything.

## Prerequisites

| Requirement | Why |
| --- | --- |
| Python ≥ 3.11 | hard requirement of `bank2ai` |
| Node.js ≥ 18 (with `npx` on `PATH`) | okgate is an npm package driven through `npx` |
| Network on first run | `npx -y -p @agentwares/agentguard` downloads the proxy once, then caches it |

## Setup

```powershell
cd banking-agent
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` pins `bank2ai==0.6.1` and `fastmcp==4.1.3`. okgate is
deliberately **not** a Python dependency — it is the npm package, pinned by the
`PACKAGE` constant in `banking_agent/gate/client.py`.

## Run it

```powershell
# All eight scenarios, with the evidence each one proves. Exit code 0 == all passed.
.venv\Scripts\python.exe -m banking_agent.demo.run

# One scenario on its own: green yellow red approval cap loop kill audit
.venv\Scripts\python.exe -m banking_agent.demo.run yellow
```

The demo resets `.okgate/` and `.state/` before each scenario, because both
okgate's caps and the daily total are cumulative — without a reset, scenario *n*
would inherit scenario *n-1*'s spend.

```powershell
.venv\Scripts\python.exe -m pytest -q
```

41 tests. The unit tests stub the proxy and pin the decisions the gate makes
*before* anything leaves the process — above all, that an unconfirmed Yellow
call never reaches okgate. The live integration is the demo's job.

## The tier rule

Track 2 §III.1 keys the tier on the **daily cumulative total**, not the single
amount:

| Tier | Condition | Behaviour |
| --- | --- | --- |
| Green | read-only tools (`get-*`) | runs automatically |
| Yellow | reversible, daily total ≤ ¥1,000 | the user confirms the details first |
| Red | daily total > ¥1,000, or an irreversible operation | strong verification (SMS code) first |
| Red | unknown tool | fail closed |

Enforced in `banking_agent/gate/tiers.py`, pinned by `tests/test_tiers.py`. The
consequence worth showing a judge: ¥600 authorised, then a ¥500 transfer, is
**Red** — a small amount promoted by the day's history.

## Where okgate ends and this package begins

This split is the design, not an accident of what the tools happen to support:

| Layer | Owner | Why not the other |
| --- | --- | --- |
| Kill switch, scope, classification, approvals, loop breaker, caps, audit chain | okgate | it is a policy proxy on the transport; it sees every call |
| Green/Yellow/Red tiers | us | okgate has no notion of a daily cumulative total |
| MFA | us | **okgate has no MFA**; Red verification must run before the call |
| Daily spend counter | us | the tier rule reads it; okgate's caps are a separate, harder ceiling |
| Audit log | okgate writes, `GateClient.verify_audit` reads | hash-chaining is okgate's |

The layers run in a fixed order in `SecureBankGate.call` — classify, MFA,
confirmation, proxy, charge — and it stops at the first refusal. A refusal is a
return value, never an exception: the same entry point serves the CLI demo and an
HTTP endpoint.

## Integrating a scenario

Every tool call goes through one primitive:

```python
async with GateClient(policy=ROOT / "okgate.yaml", root=ROOT) as client:
    gate = SecureBankGate(
        client=client,
        spend=DailySpendLedger(STATE / "daily_spend.json"),
        mfa=mfa,                       # omit only if nothing can go Red
        subject="张小伟",
    )

    outcome = await gate.call("get-transactions", {"account_id": "acc_cmb_001"})
    if not outcome.ok:
        return render(outcome)         # one shape for every refusal
```

For transfers, the two phases bank2ai defines are wrapped for you:

```python
prepared = await gate.transfer(
    debtor_account_id="acc_cmb_001", creditor=CREDITOR, amount=600, confirmed=True
)
if prepared.needs_mfa:
    return ask_for_code(prepared.prepared.details["challenge_id"])
if prepared.needs_confirmation:
    return ask_the_user(prepared.message)

settled = await gate.execute(prepared.intent_id)
if settled.needs_approval:
    show(settled.approval_command)     # the human runs it, not the agent
```

`TransferOutcome` exposes `needs_confirmation`, `needs_mfa` and `needs_approval`,
so the UI renders every state from one object.

**Adding a tool.** Add the handler in `banking_agent/bank/server.py` and register
it with `bank2ai.register_tools`. Then classify it: a `get-*` name is Green by
default, but any tool that moves money or is irreversible must be added to
`TRANSFER_TOOLS` / `CONFIRM_TOOLS` in `tiers.py` **and** to the `classify` and
`approval` blocks of `okgate.yaml`. Unknown tools fail closed, so a forgotten
registration refuses rather than slipping through.

## Operating it

```python
await client.kill("operator pressed the kill switch")  # halt everything, reads included
await client.resume()
await client.status()                                  # counters vs caps, pending approvals
await client.approve("apr_1a814e5db2")                 # a human action, never an agent action
await client.verify_audit()                            # "ok: N entries, chain intact"
```

The admin calls shell out to okgate's own CLI rather than MCP, so they are not
themselves gated — which is what you want, or a kill switch could be gated.

## Known limits

These belong in the security self-assessment; they are real, not hypothetical.

- **The bank is a mock.** `banking_agent/bank/` is an in-memory ledger. It is not
  a bank, carries no real money, and must be swapped for a conformant MCP server
  before use in production.
- **The proxy adds a Node.js runtime dependency** to a Python project. If `npx`
  is missing, every call fails closed rather than falling back to a direct
  connection — the safe direction, but a deployment constraint.
- **okgate has no native MFA.** Red-tier verification lives here, in the agent
  layer, in front of the call. It is not enforced by the same component that
  enforces the caps.
- **Currency conversion is 1:1.** `okgate.yaml` prices `prepare-transfer` in CNY
  and the policy carries a USD cap, so the mapping between them is fixed at 1:1.
  The mock bank's accounts are all CNY, so a non-CNY amount is refused by the
  bank as `currency_mismatch` before it could be mispriced — but the shortcut is
  in the policy file and is flagged there.
- **No rollback.** A settled `execute-transfer` cannot be reversed; there is no
  compensating transaction.
- **Red-tier tools from Track 2's list** (password change, lost-card report,
  investment subscription) are not in bank2ai's standardized surface yet, so
  `MFA_TOOLS` is empty. The classification hook exists; the tools do not.
