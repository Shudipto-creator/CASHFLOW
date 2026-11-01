# CASHFLOW Frontend

React 18 + Vite frontend for the CASHFLOW AI Chief Financial Officer platform.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | React 18 |
| Build Tool | Vite 5 |
| Styling | Tailwind CSS |
| Routing | React Router DOM v6 |
| HTTP Client | Axios |
| Forms | React Hook Form + Zod |
| Icons | Lucide React |
| Charts | Recharts |

## Zero-Trust Security

Every banking API request is signed client-side with Ed25519 (Web Crypto API) before it leaves the browser:

- **`src/utils/signing.js`** — Key generation (IndexedDB), canonicalization, STID computation, Ed25519 signing
- **`src/hooks/useSignedBankingApi.js`** — React hook that wraps banking API calls with signing headers (`X-Request-Signature`, `X-Request-STID`, `X-Client-Id`, `X-Request-Timestamp`, `X-Client-Public-Key`)

The backend verifies every signature before processing, then re-signs for the bank/okgate upstream.

## Security Pages

| Page | Path | Description |
|------|------|-------------|
| Security Dashboard | `/security` | Tier indicator, daily spend, kill switch, approvals, audit log |
| Banking Operations | `/banking` | Two-phase transfers with confirmation/MFA/approval states |

## Security Components

| Component | Path | Purpose |
|-----------|------|---------|
| TierBadge | `src/components/Security/TierBadge.jsx` | Green/Yellow/Red tier indicator |
| KillSwitch | `src/components/Security/KillSwitch.jsx` | Kill/resume buttons with status |
| MfaChallenge | `src/components/Security/MfaChallenge.jsx` | Enter SMS code UI |
| ApprovalList | `src/components/Security/ApprovalList.jsx` | Pending approvals with approve button |
| AuditLog | `src/components/Security/AuditLog.jsx` | Audit entries + verify chain |

## Getting Started

```bash
cd front-end
npm install
npm run dev
```

Frontend: **http://localhost:5173** | Backend API: **http://localhost:8000**

## Environment

Create `front-end/.env`:

```
VITE_API_BASE_URL=http://localhost:8000
```

## Build

```bash
npm run build
```

## Project Structure

```
front-end/
├── src/
│   ├── pages/          # Banking.jsx, Security.jsx, Dashboard.jsx, etc.
│   ├── components/     # Security/, Common/, Layout/
│   ├── context/        # AuthContext.jsx, ModeContext.jsx
│   ├── services/       # api.js (axios + banking functions)
│   ├── hooks/          # useSignedBankingApi.js
│   ├── utils/          # signing.js (Web Crypto Ed25519)
│   └── App.jsx         # Application entry point with routing
├── .env
├── package.json
├── vite.config.js
└── tailwind.config.js
```
