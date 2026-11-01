# CASHFLOW

<div align="center">

# CASHFLOW

### Autonomous AI Chief Financial Officer for SMEs

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/AWS%20Bedrock-Nova%20Lite-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white" />
  <img src="https://img.shields.io/badge/ChromaDB-Vector%20Store-8B5CF6?style=for-the-badge" />
</p>

> CASHFLOW turns raw financial documents into actionable intelligence through a pipeline of five AI agents powered by AWS Bedrock, with a Zero-Trust banking security layer for zero-trust money transfers.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Features](#features)
- [Getting Started](#getting-started)
- [Backend Setup](#backend-setup)
- [Frontend Setup](#frontend-setup)
- [Banking Security Layer Setup](#banking-security-layer-setup)
- [API Reference](#api-reference)
- [Zero-Trust Banking API](#zero-trust-banking-api)
- [Sandbox Testing](#sandbox-testing)
- [Environment Variables](#environment-variables)
- [Limitations](#limitations)
- [License](#license)

---

## Overview

**CASHFLOW** is an AI-native financial intelligence platform for small and medium enterprises. It combines document ingestion, AI-powered financial analysis, retrieval-augmented generation (RAG) over financial documents, and a production-grade Zero-Trust banking security layer for MFA-gated, kill-switch-controlled money transfers.

The system consists of three main components:

1. **Backend** (`app/`) — FastAPI application with five AI agents, document processing, RAG pipeline, dashboard analytics, and a Zero-Trust banking security bridge.
2. **Frontend** (`front-end/`) — React 18 + Vite application with dashboard, analysis, reports, banking, and security pages.
3. **Banking Security** (`banking-agent/`) — Standalone Python package implementing the Zero-Trust security layer with okgate proxy integration, tier classification (Green/Yellow/Red), MFA, confirmation, approvals, kill switch, and tamper-evident audit logging.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.9+, FastAPI, SQLite, SQLAlchemy |
| **AI / LLM** | AWS Bedrock — Amazon Nova Lite, Titan Embeddings V2 |
| **Vector Store** | ChromaDB |
| **Document Parsing** | pdfplumber, openpyxl, PyPDF2 |
| **Frontend** | React 18, Vite 5, Tailwind CSS, Recharts |
| **Auth** | JWT, bcrypt |
| **Banking Security** | Zero-Trust layer: okgate + SecureBankGate, Ed25519 request signing, Pydantic schema validation, tamper-evident audit ledger |

---

## Project Structure

```
CASHFLOW/
├── app/                          # FastAPI backend
│   ├── agents/                   # AI agents (financial, forecasting, risk, etc.)
│   ├── core/
│   │   └── security/             # Zero-Trust security infrastructure
│   │       ├── signing.py        # Ed25519 sign/verify, STID, canonicalization
│   │       ├── keys.py           # Encrypted key loading at startup
│   │       ├── audit_ledger.py   # Tamper-evident decision log
│   │       └── mtls.py           # mTLS client cert config
│   ├── routers/
│   │   ├── auth.py               # Register / login
│   │   ├── documents.py          # Upload, list, delete
│   │   ├── analysis.py           # Run analysis, fetch reports
│   │   ├── ask_cfo.py            # RAG chat endpoint (AgentCFO)
│   │   ├── dashboard.py          # Dashboard charts & insights
│   │   ├── banking.py            # Zero-trust banking endpoints (16 routes)
│   │   ├── billflow.py           # Bill flow / billing analysis
│   │   ├── portfolio.py          # Portfolio analysis
│   │   └── settings.py           # Processing mode (AWS/Local)
│   ├── schemas.py                # Pydantic models incl. transfer schemas
│   ├── scripts/
│   │   └── generate_keys.py      # One-time Ed25519 keypair generation
│   ├── services/
│   │   ├── nova_client.py        # AWS Bedrock API client
│   │   ├── embeddings.py         # ChromaDB vector store wrapper
│   │   ├── s3_service.py         # S3 file storage
│   │   ├── mode_service.py       # Processing mode service
│   │   ├── llm_factory.py        # LLM client factory
│   │   └── billflow/             # Bill flow analysis engine
│   ├── utils/
│   │   ├── pdf_parser.py
│   │   ├── excel_parser.py
│   │   ├── financial_metrics.py
│   │   └── cfo_recommendation_engine.py
│   ├── middleware/
│   │   ├── cors.py
│   │   └── error_handler.py
│   ├── main.py                   # FastAPI application entry point
│   ├── config.py                 # Application configuration
│   ├── models.py                 # Database models
│   ├── database.py               # Database session management
│   └── dependencies.py           # Auth & DB dependencies
├── banking-agent/                # Zero-Trust security layer (standalone package)
│   ├── banking_agent/
│   │   ├── config.py         # BANK_UPSTREAM_MODE: MOCK | POSTMAN_DEMO
│   │   ├── gate/
│   │   │   ├── gate.py           # SecureBankGate — tier/MFA/confirmation enforcement
│   │   │   ├── client.py         # GateClient — okgate proxy via npx
│   │   │   ├── contract.py       # GateOutcome / TransferOutcome / GateCode vocab
│   │   │   ├── mfa.py            # SmsCodeMfa — server-side code store
│   │   │   ├── daily_spend.py    # DailySpendLedger — cumulative daily total
│   │   │   └── tiers.py          # Green/Yellow/Red classification
│   │   ├── bank/
│   │   │   ├── server.py         # bank2ai MCP tools (backend chosen by mode)
│   │   │   ├── ledger.py         # In-memory ledger (MOCK backend)
│   │   │   ├── postman_adapter.py# Postman demo REST backend (POSTMAN_DEMO)
│   │   │   └── data.py           # Mock data
│   │   ├── config.py             # Bank upstream mode + demo connection settings
│   │   ├── demo/
│   │   │   └── run.py            # 8 scenario / 38-check demo
│   │   └── __init__.py
│   ├── okgate.yaml               # okgate policy — kill, caps, classification, approvals
│   ├── bank_upstream.env         # Operator switch: which bank answers behind the gate
│   ├── requirements.txt
│   ├── pytest.ini
│   └── tests/
│       ├── test_gate.py          # Unit tests
│       ├── test_tiers.py
│       ├── test_mfa.py
│       ├── test_daily_spend.py
│       ├── test_postman_adapter.py    # Adapter against the demo's verified contract
│       └── test_sandbox_integration.py# Mode switching + AgentVault detection
├── front-end/                    # React + Vite frontend
│   ├── src/
│   │   ├── pages/                # Dashboard, Analysis, Documents, Report, Banking, Security
│   │   ├── components/           # Navbar, ThemeLayout, ProtectedRoute, AskCFOChat, Security components
│   │   ├── context/              # AuthContext, ModeContext
│   │   ├── services/             # Axios API client + banking API functions
│   │   ├── hooks/                # useSignedBankingApi — Ed25519 signing wrapper
│   │   ├── utils/                # signing.js — Web Crypto API Ed25519, STID computation
│   │   └── App.jsx               # Application entry point with routing
│   ├── .env                      # VITE_API_BASE_URL
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
├── data/                         # Vector store & document data
├── uploads/                      # Document uploads
├── logs/                         # Application logs
├── scripts/
│   └── run_in_agentvault.sh      # Wrap the backend in AgentVault (credential isolation)
├── banking_agent/                # WeCom bot package (imported by app.main)
├── .gitignore                    # Git ignore rules
├── README.md                     # This file
├── WECOM_SETUP.md                # WeCom channel setup guide
└── requirements.txt              # Python dependencies
```

---

## Features

| Agent | What it does |
|-------|-------------|
| Financial Analyzer | Revenue, expenses, liabilities, margins |
| Cash Flow Forecaster | 3 & 6-month projections, burn rate, runway |
| Risk Detector | Anomalies, fraud flags, risk score |
| Compliance & Automation Agent | Multi-jurisdiction tax compliance (GST/VAT, income tax, sales tax, withholding) |
| Explainability Agent | Plain-language CFO-level recommendations |

- **Document ingestion** — PDF and Excel/CSV upload, chunked and embedded into ChromaDB
- **Ask CFO** — RAG-powered conversational Q&A over your own financial documents
- **Reports** — Full structured report per analysis run with charts and export
- **Auth** — JWT-based login with per-user document and analysis isolation
- **Zero-Trust Banking Security** — Tier classification (Green/Yellow/Red), MFA, confirmation, kill switch, audit log, two-phase transfers with approvals

---

## Getting Started

### 1 — Clone

```bash
git clone https://github.com/your-username/cashflow.git
cd cashflow
```

### 2 — Backend

```bash
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate        # macOS / Linux

pip install -r requirements.txt

copy app\.env.example app\.env  # Windows
cp app/.env.example app/.env    # macOS / Linux
```

Edit `app/.env` (minimum required values):

```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
SECRET_KEY=your_jwt_secret     # openssl rand -hex 32
```

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3 — Frontend

```bash
cd front-end
npm install
npm run dev
```

Frontend: **http://localhost:5173** | API docs: **http://localhost:8000/docs**

### 4 — AWS Bedrock

Enable these models in your region (`us-east-1`):

| Model | ID |
|-------|-----|
| Amazon Nova Lite | `global.amazon.nova-2-lite-v1:0` |
| Amazon Titan Embeddings V2 | `amazon.titan-embed-text-v2:0` |

Required IAM permissions: `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`

---

## Zero-Trust Architecture (Judges' Summary)

CASHFLOW implements a production-grade Zero-Trust security layer for banking operations. The architecture enforces **Zero Trust** principles at every layer:

### 1. Cryptographic Proof of Intent
Every banking request from the frontend is **Ed25519-signed** client-side using the Web Crypto API. The signature covers the canonicalized request body (method + path + body + client ID), producing a **Semantic Transaction ID (STID)** — a unique fingerprint that prevents replay attacks and tampering. The backend verifies every signature before processing any request.

### 2. Defense-in-Depth Architecture
Security is enforced in four independent layers:

| Layer | Component | Purpose |
|-------|-----------|---------|
| **L1** | Pydantic Schema Validation | Rejects malformed/injected payloads before they reach okgate |
| **L2** | Canonicalization + SHA-256 | Deterministic signing for all requests |
| **L3** | okgate Proxy | Enforces tier classification, MFA, confirmation, caps, loop breaker |
| **L4** | Backend Re-signing | Ed25519 signature on every call forwarded to okgate |

### 3. Tier Classification
okgate classifies every call based on daily cumulative spend:

| Tier | Condition | Behavior |
|------|-----------|----------|
| **Green** | Daily spend ≤ ¥1,000 | Execute automatically |
| **Yellow** | ¥1,000 < spend ≤ ¥5,000 | Requires user confirmation |
| **Red** | spend > ¥5,000 | Requires strong MFA verification |

### 4. RBAC (Role-Based Access Control)
Critical operations require admin privileges:

| Operation | Required Role |
|-----------|---------------|
| Kill Switch | **Admin** |
| Resume Service | **Admin** |
| All other operations | User |

Non-admin users receive `403 Forbidden` when attempting kill/resume.

### 5. Immutable Audit Log
Two independent, hash-chained audit logs provide tamper evidence:
- **okgate audit.jsonl** — okgate's native audit chain
- **Backend decision ledger** — Independent hash-chained log of all security decisions

The `verify chain` button on the Security page checks both chains for integrity.

### 6. Omnichannel: Web PWA + WeCom
To make the security layer accessible everywhere, CASHFLOW supports two channels:

- **Web PWA**: Progressive Web App installable via "Add to Home Screen" on any device
- **WeCom (企业微信)**: WeChat Work intelligent bot for Chinese enterprise users

> We explicitly chose WeCom over consumer IM platforms because our target users are bank staff and SME owners who already use WeCom daily. The WebSocket long-connection mode ensures zero network friction inside China, while our backend remains channel-agnostic — the same Zero-Trust `okgate` and cryptographic signing pipeline serves both the Web dashboard and the IM channel.

Both channels share the **same backend service functions**, ensuring identical security enforcement regardless of access method.

---

## Endpoints under `/api/banking`

All endpoints under `/api/banking` require JWT auth + Ed25519 request signing.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/banking/tools` | List gated tools (from okgate) |
| `POST` | `/api/banking/call` | Generic tool call (any tier) |
| `GET` | `/api/banking/status` | Counters vs caps, kill state |
| `GET` | `/api/banking/spend` | Today's authorised spend (CNY) |
| `GET` | `/api/banking/tier` | Tier preview without calling |
| `POST` | `/api/banking/transfer/prepare` | Phase 1: price + reserve intent |
| `POST` | `/api/banking/transfer/execute` | Phase 2: settle prepared intent |
| `POST` | `/api/banking/transfer/execute/{id}/approve` | Human approve then re-execute |
| `POST` | `/api/banking/mfa/challenge` | Start Red-tier MFA challenge |
| `GET` | `/api/banking/mfa/code/{id}` | Return delivered code (SMS sim, demo mode only) |
| `POST` | `/api/banking/mfa/verify` | Submit MFA code |
| `POST` | `/api/banking/kill` | Halt all calls (kill switch, admin only) |
| `POST` | `/api/banking/resume` | Resume after kill switch (admin only) |
| `GET` | `/api/banking/approvals` | Pending approvals |
| `GET` | `/api/banking/audit` | Audit entries (okgate) |
| `GET` | `/api/banking/audit/verify` | Verify audit chain (okgate + ledger) |
| `POST` | `/api/banking/telegram/webhook` | Telegram webhook (deprecated, use WeCom) |
| `POST` | `/api/settings/telegram/webhook` | WeCom webhook |

---

## Banking Security Backend Setup

The banking security layer lives in `banking-agent/` and is owned by the backend via FastAPI. It is **not** imported by the frontend — the frontend talks to FastAPI REST endpoints instead.

### 1 — Prerequisites

| Requirement | Why |
|-------------|-----|
| Python ≥ 3.11 | Required by bank2ai |
| Node.js ≥ 18 (with `npx` on PATH) | okgate runs as an npm package via `npx` |
| Network on first run | `npx -y -p @agentwares/agentguard` downloads okgate once |

### 2 — Setup

```bash
cd banking-agent
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt   # Windows
source .venv/bin/activate && pip install -r requirements.txt  # macOS / Linux
```

### 3 — Run tests

```bash
cd banking-agent
.venv\Scripts\python.exe -m pytest -q        # 78 passed, 1 skipped (Windows)
source .venv/bin/activate && python -m pytest -q  # macOS / Linux
```

### 4 — Run demo (live against okgate proxy)

```bash
.venv\Scripts\python.exe -m banking_agent.demo.run   # 38/38 checks pass
```

### 5 — Backend startup

```bash
cd <repo-root>
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Set `KEY_PASSPHRASE` in `app/.env` for Ed25519 signing key decryption at startup:

```bash
KEY_PASSPHRASE=your-passphrase python app/scripts/generate_keys.py
```

---

## Sandbox Testing

Two external sandboxes validate the Zero-Trust layer from opposite directions: the **Postman Banking-API-Demo** proves the tool surface works against a real, stateful REST bank (functional), and **AgentVault** proves the backend process can be denied credentials it is not allowed to hold (isolation).

```
frontend / agent
   └── okgate proxy          ← tiers, ¥5,000/day cap, loop breaker, kill, audit
         └── SecureBankGate  ← MFA, confirmation, daily spend ledger
               └── bank2ai tools        ← names never change (the invariant)
                     ├── Ledger            (MOCK)
                     └── PostmanBankBackend (POSTMAN_DEMO)   ← sandbox sits here
```

Both sandboxes plug in **below** the security layer. `SecureBankGate` and `okgate.yaml` are untouched, so a security result measured in either sandbox means exactly what it means in production.

### 1 — Postman Banking-API-Demo (functional)

Proves the `bank2ai` handlers can drive a live HTTP bank instead of the in-memory ledger.

```bash
git clone https://github.com/Postman-Devrel/Banking-API-Demo postman-demo
cd postman-demo
npm install            # requires Node 20+
npm run dev            # all three services (banking :3000, fraud :8080, support :8090)
npm run dev:api        # just the banking API on :3000 — enough for CASHFLOW
```

Point CASHFLOW's bank upstream at it — no code change, no `okgate.yaml` change.
Exporting the variable is **not** enough once the gate is in front: okgate spawns the
bank with the MCP SDK's default environment plus only the keys declared in
`okgate.yaml`'s `upstreams[].env`, so a shell variable never reaches it. The switch is
the operator-owned `banking-agent/bank_upstream.env` (same trust story as `okgate.yaml`
— a human edits it, the agent does not):

```bash
# banking-agent/bank_upstream.env
BANK_UPSTREAM_MODE=postman_demo
POSTMAN_DEMO_BASE_URL=http://127.0.0.1:3000
POSTMAN_DEMO_ALLOW_CURRENCY_ALIAS=1   # the demo script speaks CNY; see the currency note

cd banking-agent
python -m banking_agent.demo.run      # same 38 checks, now over REST
```

The proxy echoes the choice on stderr for every run, which is how you confirm it took
effect rather than silently falling back to the mock:

```
[okgate] bank: bank upstream: POSTMAN_DEMO -> http://127.0.0.1:3000 (prefix /api/v1)
[okgate] connected 1/1 upstreams, 9 tools, mode enforce
```

Each key can be set in the process environment or in `banking-agent/bank_upstream.env`;
the environment wins, which is what makes a one-off standalone run
(`BANK_UPSTREAM_MODE=postman_demo python -m banking_agent.bank.server`) work without
touching the file. Defaults below are what the code uses when neither is set.

| Setting | Default | Notes |
|---------|---------|-------|
| `BANK_UPSTREAM_MODE` | `mock` | `mock` \| `postman_demo`. An unrecognised value fails closed to `mock` — a typo must not reach a live bank. |
| `POSTMAN_DEMO_BASE_URL` | `http://localhost:3000` | Banking service of the demo. Use `127.0.0.1` on Windows: the demo listens on IPv4 and a `::1`-first lookup surfaces as "not running". |
| `POSTMAN_DEMO_API_PREFIX` | `/api/v1` | The demo mounts its routers under `/api/v1`; the bare `/accounts` paths 404. |
| `POSTMAN_DEMO_API_KEY` | `1234` | Demo customer key; admin is `admin-demo-key`. Sent as `x-api-key`. |
| `POSTMAN_DEMO_TRANSFER_PATH` | `/api/v1/transactions` | The demo has **no transfers route** — a money movement is `POST /api/v1/transactions` ("post an atomic transfer or deposit"). Override here if your fork renames it. |
| `POSTMAN_DEMO_TRANSACTIONS_PATH` | `/api/v1/transactions` | Read side. |
| `POSTMAN_DEMO_CURRENCY` | `COSMIC_COINS` | The amount the adapter posts. Must be one of the demo's enum: `COSMIC_COINS` / `GALAXY_GOLD` / `MOON_BUCKS`. |
| `POSTMAN_DEMO_ALLOW_CURRENCY_ALIAS` | `0` | Off by default. When `1`, the caller's currency label is treated as decorative and the transfer settles in the account's own token — a functional demo of the flow, **not** a monetary-accurate one. `banking_agent/demo/run.py` is written in CNY, so it needs this on to complete against the demo. See below. |
| `POSTMAN_DEMO_RUN_ID` | *(unset)* | Sent as `x-demo-run-id` so a judge can tie calls to one recorded session. |
| `POSTMAN_DEMO_TIMEOUT_S` | `10` | |

**Reading the demo's contract honestly.** Everything above comes from `apps/banking-api/openapi/openapi.yaml` and `src/server.js` in that repo, and three of its rules shaped the adapter:

- Amounts are **non-negative integers in minor units**. `to_minor_units()` converts at the boundary, so the agent, `prepare-transfer`'s `amount` argument and the ¥1,000 / ¥5,000 tiers all keep working in major units while the wire stays integer.
- Requests use `additionalProperties: false`, and the recipient field is `toAccountId`, which must name an account that already exists. `prepare-transfer` therefore resolves the creditor to a real `accountId` *before* the gate asks for approval; an unspendable intent never reaches `execute-transfer` (`unknown_recipient`).
- The currency enum contains no CNY, and bank2ai validates `^[A-Z]{3}$`. So `COSMIC_COINS` is denominated on the wire and shown to the agent as `COS`. A CNY transfer against a token balance would silently reinterpret every threshold in `okgate.yaml`, so the default is to refuse with `currency_mismatch` and name the flag that would override it.

**Why the adapter defers `httpx`.** okgate gives an upstream 15s (`connectTimeoutMs`, hard-coded in `@agentwares/agentguard`) to finish the MCP handshake; if it misses, every later call in the run answers `no upstream exposes a tool named "…"`. Importing `httpx` costs ~4s cold and `httpx.AsyncClient()` another ~7s because it builds a TLS context from the OS certificate store — enough to take an otherwise-passing mock run to 12s and blow the budget. `tools/list` needs no HTTP client, so the import lives in `_httpx()` and the client is built on the first request. If you add another bank adapter behind this gate, keep its heavy imports off the startup path for the same reason.

Verify:

```bash
cd banking-agent
python -m pytest tests/test_postman_adapter.py -q          # 19 passed, 1 skipped
POSTMAN_DEMO_LIVE=1 python -m pytest tests/test_postman_adapter.py -k live -q   # against the running demo
python -m pytest tests/test_sandbox_integration.py -q      # 18 passed — mode switching + detection
python -m pytest -q                                        # 78 passed, 1 skipped
```

The default tests drive an in-process `httpx.MockTransport` that replays the verified contract above — including `additionalProperties: false`, the integer-minor-unit check and the currency enum — so CI fails if a payload shape drifts, without needing Node. The `POSTMAN_DEMO_LIVE`-gated test is the one that talks to the real service.

**Why the two-phase split is kept.** The demo settles money in one call, and `PostmanBankClient.execute_transfer(amount, to_account)` exists for direct functional testing. The MCP tool surface deliberately does **not** expose it: okgate prices money from `prepare-transfer`'s `amount` argument (`spend.tools.prepare-transfer.amount_arg: amount`) and treats `execute-transfer` as "irreversible, but not priceable". A single-call money tool would commit before the gate ever saw a price, and the ¥1,000 / ¥5,000 thresholds would stop counting real outflows. `tests/test_postman_adapter.py::test_prepare_prices_without_moving_money` guards that ordering.

### 2 — AgentVault (credential isolation)

```bash
npm install -g @inflectiv-ai/agentvault    # run the install yourself: global npm installs are machine-wide
agentvault init                            # creates .agentvault/ + built-in profiles
scripts/run_in_agentvault.sh               # wraps uvicorn with -p restrictive
# or the raw command:
agentvault wrap -p restrictive "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
```

Then, from another terminal:

```bash
curl http://localhost:8000/health
# {"status":"ok","sandbox":"agentvault","sandbox_profile":"restrictive",
#  "sandbox_markers":["AGENTVAULT_SESSION","AGENTVAULT_PROFILE","AGENTVAULT_TRUST"], ...}
```

`/health` is a lean probe that reports the wrapper; `/api/health` still does the AWS/Ollama checks. The startup log emits `Running outside AgentVault sandbox. Security isolation is not active.` whenever the markers are absent, and every response carries `X-Sandbox`.

**What this proves — and what it does not.** Read `@inflectiv-ai/agentvault@1.0.1`'s `dist/sandbox/runSandboxed.js` and you find the "sandbox" is:

```js
spawn(parts[0], parts.slice(1), { env, stdio: 'inherit', shell: true })
```

`-p restrictive` rebuilds the environment from scratch, letting through only `PATH/HOME/USER/SHELL/TERM/LANG/LC_ALL/TMPDIR/NODE_PATH` plus profile-allowed vault secrets, and injects `AGENTVAULT_SESSION/PROFILE/TRUST`. There is no namespace, firewall, proxy or `sandbox-exec`/`firejail` anywhere in the package, and its own README describes it as an encrypted credential vault.

- ✅ **Credential isolation — proven.** The wrapped process cannot read env secrets the profile denies.
- ❌ **Network isolation — not provided by this tool.** `curl` reaching the wrapped backend is the *expected* result, not a failed test; nothing in AgentVault blocks ingress or egress. Note also that `app/.env` is loaded from disk by python-dotenv inside the process, so parent-env filtering alone does not hide those values — use `MIRROR_DOTENV_TO_VAULT=1` in the script to move them into the vault and let the profile deny them explicitly.
- **The network control plane remains okgate**: the agent never holds a handle on the bank upstream, and `classify.unknown: block` refuses any tool nobody classified. That is the bypass claim to demonstrate.

Honest bypass demo for the judges (works with or without AgentVault):

```bash
# 1. an unclassified money tool is refused outright (fail closed)
# 2. the kill switch stops everything, including reads
echo kill > banking-agent/.okgate/KILL
# 3. the ¥5,000/day cap rejects the sixth ¥1,000 transfer of the day
```

### Backend-agnostic by construction

Whichever backend answers, `build_server()` registers the identical nine tools — `get-accounts`, `get-transactions`, `get-transaction`, `get-categories`, `get-transactions-summary`, `get-recipients`, `create-recipient`, `prepare-transfer`, `execute-transfer` — with the same bank2ai input schemas and response models (`tests/test_sandbox_integration.py` asserts the sets are equal in both modes). okgate's `classify` rules key off those names, and the frontend's Ed25519-signed `/api/banking/*` calls never learn which bank answered. Adding a real bank means writing a third backend with the same handler signatures — exactly what these two sandboxes demonstrate.

| Failure mode | Behaviour |
|--------------|-----------|
| Demo not running | `ToolResult(status="error", message="Postman Demo API is not running. Please start it with \`npm run dev\`.")`; on the MCP surface a `BankUnavailableError` is raised so the gate records a refusal. |
| Demo hangs | Timeout reported distinctly from downtime, so operators are not told to restart a healthy service. |
| Wrong `x-api-key` | Reported as `401`, never as "service down". |
| Payload the demo rejects | `400` with the demo's own message surfaced in `detail`. The adapter posts the shapes its schema declares — integer minor units, only known keys, an enum currency — so a regression here shows up as a refusal, not a silently coerced amount. |
| Currency the demo does not offer | `prepare-transfer` returns `currency_mismatch` and names `POSTMAN_DEMO_ALLOW_CURRENCY_ALIAS`; it never re-denominates a ¥ instruction into a token behind the gate's back. |
| Recipient with no demo account | `prepare-transfer` returns `unknown_recipient`, so approval is never requested for a transfer that cannot be posted. |
| Reads against a dead bank | Raises instead of returning an empty list — an unreachable bank must not look like a broke customer. |
| Outside AgentVault | Startup warning + `X-Sandbox: none` + `/health` reports `sandbox: "none"`. |

---

## Environment Variables

```env
# AWS
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1

# App
APP_ENV=development
DEBUG=true
SECRET_KEY=
JWT_EXPIRATION_HOURS=24

# Database
DATABASE_URL=sqlite:///./data/cashflow.db

# Storage
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE_MB=10
VECTOR_STORE_PATH=./data/vector_store

# Server
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:5173

# Models (defaults pre-set in config.py)
NOVA_LITE_MODEL_ID=global.amazon.nova-2-lite-v1:0
EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0

# Zero-Trust banking security layer
# Generate once: KEY_PASSPHRASE='...' python app/scripts/generate_keys.py
KEY_PASSPHRASE=your_key_passphrase_here
BACKEND_SIGNING_KEY_ID=banking-backend-v1
BANK_CLIENT_CERT_PATH=app/secrets/bank-client-cert.pem
BANK_CLIENT_KEY_PATH=app/secrets/bank-client-key.pem
BANK_CA_CERT_PATH=app/secrets/bank-ca-cert.pem

# Sandbox testing (see "Sandbox Testing")
BANK_UPSTREAM_MODE=mock            # mock | postman_demo
POSTMAN_DEMO_BASE_URL=http://localhost:3000
POSTMAN_DEMO_API_PREFIX=/api/v1
POSTMAN_DEMO_API_KEY=1234
POSTMAN_DEMO_TRANSFER_PATH=/api/v1/transactions   # the demo has no /transfers route
POSTMAN_DEMO_CURRENCY=COSMIC_COINS                # COSMIC_COINS | GALAXY_GOLD | MOON_BUCKS
POSTMAN_DEMO_ALLOW_CURRENCY_ALIAS=0               # 1 = settle in the account's own token
POSTMAN_DEMO_RUN_ID=                              # sent as x-demo-run-id
POSTMAN_DEMO_TIMEOUT_S=10
```

---

## Limitations

- **Single-document analysis only** — the Analysis page supports selecting one document per run; multi-document batch analysis is not exposed in the UI
- **SQLite backend** — suitable for development and single-user use; not recommended for concurrent multi-user production deployments
- **No real-time streaming** — agent responses are returned as a single payload after all five agents complete; there is no token-by-token streaming to the frontend
- **Multi-jurisdiction tax compliance** — the Compliance & Automation Agent supports GST/VAT, income tax, sales tax, withholding tax across China, the United States, India, and other jurisdictions; jurisdiction-specific rules are configurable per tenant
- **AWS region dependency** — Nova Lite and Titan Embeddings V2 must be enabled in your selected AWS region; cross-region inference is required for Nova Lite
- **No file versioning** — re-uploading a document with the same name creates a new record; there is no deduplication or version history
- **No scheduled runs** — analyses must be triggered manually; there is no cron-based or event-driven automation
- **Ask CFO context window** — RAG retrieval is limited to the top-k chunks in ChromaDB; very large documents may lose precision if relevant chunks fall outside the retrieved set

---

## License

MIT License

Copyright © 2026 CASHFLOW. All rights reserved.
