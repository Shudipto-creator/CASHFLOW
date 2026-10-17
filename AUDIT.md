# CASHFLOW Phase 1 Audit

## Backend (FastAPI + SQLAlchemy + SQLite + ChromaDB)
- `app/main.py` — app factory, includes auth, analysis, documents, ask_cfo, dashboard routers
- `app/config.py` — settings with AWS Bedrock model IDs
- `app/database.py` — SQLite engine, session factory, base model
- `app/models.py` — User, Analysis, Document, ChatThread, ChatMessage, Artifact models
- `app/schemas.py` — Pydantic schemas for all models
- `app/dependencies.py` — get_db, get_current_user, get_current_user_id
- `app/utils/auth.py` — bcrypt, JWT, password hashing
- `app/utils/financial_metrics.py` — burn rate, runway, categorization, loan readiness
- `app/utils/pdf_parser.py` — pdfplumber + PyPDF2 extraction
- `app/utils/excel_parser.py` — openpyxl + xlrd extraction
- `app/utils/cfo_recommendation_engine.py` — deterministic CFO recommendations
- `app/services/embeddings.py` — ChromaDB vector store
- `app/services/nova_client.py` — AWS Bedrock client (only provider)
- `app/agents/base_agent.py` — BaseAgent ABC
- `app/agents/financial_analyzer.py` — Agent 1: financial extraction
- `app/agents/cashflow_forecaster.py` — Agent 2: cash flow forecasting
- `app/agents/risk_detector.py` — Agent 3: risk detection
- `app/agents/automation_agent.py` — Agent 4: compliance/automation (India-focused: GST, TDS)
- `app/agents/explainability_agent.py` — Agent 5: explainability
- `app/services/s3_service.py` — stub for future S3
- `app/middleware/cors.py` — CORS setup
- `app/middleware/error_handler.py` — global error handlers
- `app/routers/auth.py` — register, login, get_me
- `app/routers/documents.py` — upload, list, delete, extract
- `app/routers/analysis.py` — run analysis, list, get
- `app/routers/ask_cfo.py` — ask CFO questions
- `app/routers/dashboard.py` — dashboard stats

## Frontend (React 18 + Vite + Tailwind + Recharts)
- Retro green-on-black terminal theme with monospace fonts
- `App.jsx` — routes: /, /login, /register, /dashboard, /analysis, /report/:id, /reports, /financial-intelligence, /documents
- `ThemeLayout.jsx` — terminal shell with scanlines, CRT effects
- `Navbar.jsx` — monochrome nav with AgentCFO branding
- `AuthContext.jsx` — JWT auth context
- `api.js` — axios client with JWT interceptor
- Pages: Dashboard, Analysis, Documents, Reports, Report, FinancialIntelligence, Login, Register
- Components: AskCFOChat, ProtectedRoute, LoadingSpinner
- Tailwind config uses retro colors (primary #1e40af)

## Issues found
1. Product named "AgentCFO" / "CFONE" — must rename to CASHFLOW
2. Retro terminal theme — must replace with navy/teal design system
3. Single LLM provider (Bedrock only) — must add abstraction with mock mode
4. No Organization model — must add for multi-tenant support
5. India-only logic in automation_agent (GST, TDS) — must make jurisdiction-configurable
6. No Alembic migrations — must add
7. No Docker setup — excluded per user request
8. No i18n — must add react-i18next
9. Sample data mentions KJSCE Technologies — must replace with synthetic demo
10. No public site, legal pages, favicon, or launch gate
11. No forecast engine, financing matcher, alerts, or audit chain
12. No tool layer, policy engine, or approvals system
13. No injection defense or masking
14. No tests