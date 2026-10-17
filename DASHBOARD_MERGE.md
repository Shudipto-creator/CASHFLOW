# Dashboard Merge Inventory

| Widget or metric | Source page | Endpoint feeding it | Keep or drop | Why |
|---|---|---|---|---|
| greeting with user and organization | Dashboard | /api/auth/me | keep | merged header |
| date range selector 7/30/90 | FinancialIntelligence | none | keep | user driven |
| cash balance KPI | Dashboard | /api/dashboard | keep | primary metric |
| cash runway weeks KPI | Dashboard | /api/dashboard | keep | primary metric |
| receivables outstanding + overdue KPI | new | /api/invoices | keep | primary metric |
| payables due 30 days KPI | new | /api/invoices | keep | primary metric |
| 13 week forecast chart base, low, high | FinancialIntelligence | /api/forecasts | keep | core story |
| alerts card latest 5 open | Alerts | /api/alerts | keep | action signal |
| financing top recommended option | Financing | /api/financing | keep | action signal |
| approvals pending count + 3 items | Approvals | /api/approvals | keep | action signal |
| receivables aging bars | new | /api/invoices (derived) | keep | credit risk |
| spending by category horizontal bars | Dashboard | /api/dashboard | keep | cost visibility |
| risk score and flagged transactions | Risk Detector | /api/analysis | keep | risk visibility |
| plain language summary + timestamp | Explainability | /api/analysis | keep | trust |
| recent transactions 10 rows | Transactions | /api/transactions | keep | recency |
| revenue waterfall (old) | FinancialIntelligence | /api/dashboard | drop | replaced by forecast |
| rolling revenue trend | FinancialIntelligence | /api/dashboard | drop | replaced by forecast |
| loan readiness trend | FinancialIntelligence | /api/dashboard | drop | moved to Financing |
| analyze insight cards | FinancialIntelligence | /api/dashboard/insights | drop | markdown removed |
