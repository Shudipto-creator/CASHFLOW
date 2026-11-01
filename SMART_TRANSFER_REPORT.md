# Scenario 1 — Smart Transfer: LLM Banking Agent

**Branch:** `main` · **Date:** 2026-11-01 · **Author:** Doubao agent

This report documents how *Scenario 1: Smart Transfer* was completed for the
LLM banking agent in **Track 2 — "AI Agent for Banks"**. The agent takes a plain
message ("transfer ¥600 to 李娜"), uses **RAG** to stay in context of the
operations the bank can actually perform, maps the message onto **one
registered operation**, and executes it through the Zero-Trust banking gate —
**without ever letting the LLM invent an operation**.

---

## 1. What I checked first

- **Read the project** — `CASHFLOW` layout: `app/` (FastAPI + services + routes),
  `banking-agent/` (the Zero-Trust gate: `okgate` proxy + tier rules + MFA +
  `bank2ai` mock bank), `banking_agent/` (WeCom bot).
- **Last update on `main`** — commit `bedb99d` *"FX and Wecom bot"* (SHUDIPTO,
  2026-10-29) added FX endpoints (`fx/convert`, `fx/rates`) and the WeCom bot.
- **Available banking operations** (the surface that is actually implemented and
  wired up):

  | Operation | Kind | Tier | Implemented where |
  |---|---|---|---|
  | `get-accounts` | read | Green (auto) | `bank2ai` tool via okgate |
  | `get-transactions` | read | Green | `bank2ai` via okgate |
  | `get-transaction` | read | Green | `bank2ai` via okgate |
  | `get-categories` | read | Green | `bank2ai` via okgate |
  | `get-transactions-summary` | read | Green | `bank2ai` via okgate |
  | `get-recipients` | read | Green | `bank2ai` via okgate |
  | `create-recipient` | confirm | Yellow (confirm) | `bank2ai` via okgate |
  | `prepare-transfer` | transfer | Yellow/Red by daily total | `bank2ai` via okgate |
  | `execute-transfer` | confirm | Yellow (approval) | `bank2ai` via okgate |
  | `kill` / `resume` | admin | Admin CLI | `GateClient` |
  | `fx/convert` / `fx/rates` | fx | REST router | `banking.py` |

  Track-2 strong-verification operations (password change, lost-card, investment
  subscription) are **not** in the `bank2ai` surface yet (`MFA_TOOLS` is empty in
  `tiers.py`), so they are deliberately absent from the registry.

---

## 2. What I built

### `app/services/llm_banking_agent.py` — the agent (new)
The core deliverable. It implements the retrieve → select → **guard** → execute
pipeline:

1. **`BANKING_OPERATIONS`** — the single authoritative registry of the
   implemented operations above. This is the *only* key set the executor accepts.
2. **`OperationRag`** — a **RAG** index over the operations catalog (a dedicated
   ChromaDB collection, `banking_operations`). For any message it retrieves the
   operations that are actually available, so the model stays in context of what
   the bank can do. Falls back to lexical retrieval if the store is down.
3. **Selectors** — `LLMSelector` (system prompt hard-constrains the model to
   choose only from the retrieved/registered list) and a deterministic
   `DeterministicSelector` fallback for offline runs.
4. **The hard guard (the key constraint)** — after the selector proposes an
   operation, the agent re-checks the proposed id against `BANKING_OPERATIONS`.
   **If the id is not registered → the agent replies "operation not implemented"
   and never executes anything.** The LLM is free to propose but cannot create:
   execution is only dispatched by a dict lookup against the registry.
5. **`BankingExecutor`** — executes a registered operation via
   `SecureBankGate` (the gate is the *only* route to the bank), preserving tier
   classification, MFA, confirmation, okgate caps/approvals and audit.

### `app/routers/banking_agent.py` — "send a message to the agent" (new)
`POST /api/banking/agent/chat` — JWT-authenticated endpoint that takes a message
and returns the agent's action (`implemented`, `code`, `operation_id`, `message`,
`retrieved_operations`, `execution`, …). Wired into `app/main.py`.

### `app/scripts/demo_smart_transfer.py` — the runnable scenario (new)
Sends three messages to the agent and asserts the outcomes (see §4).

---

## 3. How the "don't create operations" rule is enforced

Two layers, both mandatory:

- **At selection time** — `LLMSelector` is told it *may only* answer with an
  operation present in the provided list and must return
  `{"operation_id": null, "not_implemented": true}` when nothing fits. The
  deterministic selector likewise can only ever pick registry ids.
- **At the security boundary** — `LLMBankingAgent.handle` re-validates the
  proposed id with `BANKING_OPERATIONS.get(...)` before the executor is touched.
  Any id that is not a registered operation produces
  `code = NOT_IMPLEMENTED` and no call is made.

This is proven by a hostile-LLM test in the demo: a fake model that proposes
`get-crypto-balance` (a non-existent operation) is refused with a
"not implemented" message and nothing is executed.

---

## 4. Running the scenario (verified)

Run from the repo root with the banking-agent venv:

```
banking-agent\.venv\Scripts\python.exe app\scripts\demo_smart_transfer.py
```

Result (all checks passed, exit 0):

| Step | Message | Agent decision | Outcome |
|---|---|---|---|
| 1 | `transfer ¥600 to 李娜` | `prepare-transfer` (RAG top hit) | **Yellow** tier → `CONFIRMATION_REQUIRED`; on confirm → intent `intent_978d06df…dc7` reserved, tier yellow |
| 2 | `change my password` | no registered op matches | `NOT_IMPLEMENTED` message; nothing executed |
| 3 | hostile LLM proposes `get-crypto-balance` | id not in registry | `NOT_IMPLEMENTED`; invented op never executed |

The ¥600 transfer was classified **Yellow** (within the ¥1,000 daily ceiling) and
was held for user confirmation before an intent was reserved — the exact
Track-2 tier behaviour, applied by an LLM agent.

---

## 5. Environment work that made it run

This machine had two pre-existing issues that the project's own gate demo could
not run through:

1. **Upstream `python` resolution.** `okgate.yaml` spawns the mock bank as
   `python -m banking_agent.bank.server`; here `python` resolves to a system
   interpreter without `bank2ai`, so the proxy dropped the connection. I did
   **not** edit the trust-boundary `okgate.yaml`. Instead the demo generates
   `banking-agent/okgate.work.yaml` (a copy whose upstream command is the venv's
   absolute interpreter) and `banking-agent/okgate.work.yaml` is git-ignored.
2. **`npx` path with spaces.** `npx` lives under
   `C:\Users\…\Doubao\User Data\…` and the gate spawns it through `cmd /c`, which
   splits the path. `BankingExecutor` now auto-emits a space-free `npx.cmd` shim
   in the state dir and hands it to the gate.

Both workarounds live in the new code (`llm_banking_agent.py`) and leave the
project's policy/trust files untouched. On a machine where `python` has `bank2ai`
and `npx` is on a clean path, the gate runs with the real `okgate.yaml` unchanged.

---

## 6. Files added / changed

| File | Change |
|---|---|
| `app/services/llm_banking_agent.py` | **new** — registry, RAG, selectors, guard, executor |
| `app/routers/banking_agent.py` | **new** — `POST /api/banking/agent/chat` |
| `app/scripts/demo_smart_transfer.py` | **new** — runnable scenario |
| `app/main.py` | import + include the agent router |
| `banking-agent/.venv/` | **new venv** with `bank2ai`, `fastmcp`, `chromadb`, `httpx`, `cryptography` |
| `requirements-smart-transfer.txt` | **new** — packages used by this feature |
| `SMART_TRANSFER_REPORT.md` | this report |
| `.gitignore` | ignore generated `banking-agent/okgate.work.yaml` |

## 7. Notes / limitations

- **RAG** uses ChromaDB with its default ONNX embedding function, so it works
  fully offline. In production you can swap in Titan/Ollama embeddings via the
  app's embedding client without changing the retrieval code.
- **LLM selector** calls the configured model (Nova/Ollama via `llm_factory`).
  When no model is reachable the agent transparently falls back to the
  deterministic selector — the guard holds either way.
- **FX** endpoints are registered (implemented) but return a live rate only when
  `EXCHANGERATE_API_KEY` is configured.
- **REST endpoint venv**: `fastapi` and `fastmcp` cannot share one venv
  (`starlette` version conflict), so the HTTP endpoint runs in the app venv while
  the gate runs in `banking-agent/.venv` — a pre-existing project constraint, not
  introduced here.
