<div align="center">

# CFOne

### Autonomous AI Chief Financial Officer for SMEs

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/AWS%20Bedrock-Nova%20Lite-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white" />
  <img src="https://img.shields.io/badge/ChromaDB-Vector%20Store-8B5CF6?style=for-the-badge" />
</p>

> CFOne turns raw financial documents into actionable intelligence through a pipeline of five AI agents powered by AWS Bedrock.

</div>

---

## Tech Stack

| Layer                | Technology                                          |
| -------------------- | --------------------------------------------------- |
| **Backend**          | Python 3.9+, FastAPI, SQLite, SQLAlchemy            |
| **AI / LLM**         | AWS Bedrock — Amazon Nova Lite, Titan Embeddings V2 |
| **Vector Store**     | ChromaDB                                            |
| **Document Parsing** | pdfplumber, openpyxl                                |
| **Frontend**         | React 18, Vite 5, Tailwind CSS, Recharts            |
| **Auth**             | JWT, bcrypt                                         |

---

## Project Structure

```
CFOne/
├── app/
│   ├── agents/
│   │   ├── base_agent.py               # Shared agent base class
│   │   ├── financial_analyzer.py       # Extracts revenue, expenses, margins
│   │   ├── cashflow_forecaster.py      # 3/6-month cash flow projections
│   │   ├── risk_detector.py            # Anomaly and fraud detection
│   │   ├── automation_agent.py         # GST/tax compliance & automation
│   │   └── explainability_agent.py     # Plain-language CFO summaries
│   ├── routers/
│   │   ├── auth.py                     # Register / login
│   │   ├── documents.py                # Upload, list, delete
│   │   ├── analysis.py                 # Run analysis, fetch reports
│   │   ├── ask_cfo.py                  # RAG chat endpoint
│   │   └── dashboard.py                # Stats endpoint
│   ├── services/
│   │   ├── nova_client.py              # AWS Bedrock API client
│   │   ├── embeddings.py               # ChromaDB vector store wrapper
│   │   └── s3_service.py
│   ├── utils/
│   │   ├── pdf_parser.py
│   │   ├── excel_parser.py
│   │   ├── financial_metrics.py        # Loan readiness, ratios
│   │   └── cfo_recommendation_engine.py
│   ├── middleware/
│   │   ├── cors.py
│   │   └── error_handler.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   └── dependencies.py
├── frontend/
│   └── src/
│       ├── pages/               # Dashboard, Analysis, Documents, Report, FinancialIntelligence, Reports
│       ├── components/          # Navbar, ThemeLayout, ProtectedRoute, AskCFOChat
│       ├── context/             # AuthContext
│       └── services/            # Axios API client
├── data/
│   └── vector_store/
├── uploads/
├── logs/
└── requirements.txt
```

---

## Features

| Agent                         | What it does                               |
| ----------------------------- | ------------------------------------------ |
| Financial Analyzer            | Revenue, expenses, liabilities, margins    |
| Cash Flow Forecaster          | 3 & 6-month projections, burn rate, runway |
| Risk Detector                 | Anomalies, fraud flags, risk score         |
| Compliance & Automation Agent | GST/tax deadlines, automation suggestions  |
| Explainability Agent          | Plain-language CFO-level recommendations   |

- **Document ingestion** — PDF and Excel/CSV upload, chunked and embedded into ChromaDB
- **Ask CFO** — RAG-powered conversational Q&A over your own financial documents
- **Reports** — Full structured report per analysis run with charts and export
- **Auth** — JWT-based login with per-user document and analysis isolation

---

## Getting Started

### 1 — Clone

```bash
git clone https://github.com/your-username/cfone.git
cd cfone
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
cd frontend
npm install
npm run dev
```

Frontend: **http://localhost:5173** | API docs: **http://localhost:8000/docs**

### 4 — AWS Bedrock

Enable these models in your region (`us-east-1`):

| Model                      | ID                               |
| -------------------------- | -------------------------------- |
| Amazon Nova Lite           | `global.amazon.nova-2-lite-v1:0` |
| Amazon Titan Embeddings V2 | `amazon.titan-embed-text-v2:0`   |

Required IAM permissions: `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`

---

## API Reference

| Method   | Endpoint                | Description               |
| -------- | ----------------------- | ------------------------- |
| `POST`   | `/api/auth/register`    | Register a new user       |
| `POST`   | `/api/auth/login`       | Login and get JWT         |
| `POST`   | `/api/documents/upload` | Upload PDF or Excel       |
| `GET`    | `/api/documents`        | List documents            |
| `DELETE` | `/api/documents/{id}`   | Delete document           |
| `POST`   | `/api/analysis/run`     | Start analysis (5 agents) |
| `GET`    | `/api/analysis`         | List past analyses        |
| `GET`    | `/api/analysis/{id}`    | Get full report           |
| `POST`   | `/api/ask-cfo`          | Ask a question (RAG)      |
| `GET`    | `/api/health`           | Health check              |

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
DATABASE_URL=sqlite:///./data/cfone.db

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
```

---

## Limitations

- **Single-document analysis only** — the Analysis page supports selecting one document per run; multi-document batch analysis is not exposed in the UI
- **SQLite backend** — suitable for development and single-user use; not recommended for concurrent multi-user production deployments
- **No real-time streaming** — agent responses are returned as a single payload after all five agents complete; there is no token-by-token streaming to the frontend
- **Indian tax compliance only** — the Compliance & Automation Agent is tuned for GST, TDS, and Indian Income Tax; other jurisdictions are not covered
- **AWS region dependency** — Nova Lite and Titan Embeddings V2 must be enabled in your selected AWS region; cross-region inference is required for Nova Lite
- **No file versioning** — re-uploading a document with the same name creates a new record; there is no deduplication or version history
- **No scheduled runs** — analyses must be triggered manually; there is no cron-based or event-driven automation
- **Ask CFO context window** — RAG retrieval is limited to the top-k chunks in ChromaDB; very large documents may lose precision if relevant chunks fall outside the retrieved set

---

## License

Copyright © 2026 CFOne. All rights reserved.
