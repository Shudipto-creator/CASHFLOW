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
│   │   ├── gate/
│   │   │   ├── gate.py           # SecureBankGate — tier/MFA/confirmation enforcement
│   │   │   ├── client.py         # GateClient — okgate proxy via npx
│   │   │   ├── contract.py       # GateOutcome / TransferOutcome / GateCode vocab
│   │   │   ├── mfa.py            # SmsCodeMfa — server-side code store
│   │   │   ├── daily_spend.py    # DailySpendLedger — cumulative daily total
│   │   │   └── tiers.py          # Green/Yellow/Red classification
│   │   ├── bank/
│   │   │   ├── server.py         # Mock bank + bank2ai MCP tools
│   │   │   ├── ledger.py         # In-memory ledger
│   │   │   └── data.py           # Mock data
│   │   ├── demo/
│   │   │   └── run.py            # 8 scenario / 38-check demo
│   │   └── __init__.py
│   ├── okgate.yaml               # okgate policy — kill, caps, classification, approvals
│   ├── requirements.txt
│   ├── pytest.ini
│   └── tests/
│       ├── test_gate.py          # Unit tests
│       ├── test_tiers.py
│       ├── test_mfa.py
│       └── test_daily_spend.py
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
.venv\Scripts\python.exe -m pytest -q        # 41/41 pass (Windows)
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
