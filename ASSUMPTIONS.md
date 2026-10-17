# Assumptions

- Demo accounts and demo company can be created on first login; no real bank connector is implemented. CASHFLOW only imports files the user supplies.
- Refresh token is stored in an httpOnly cookie with a 7 day lifetime. Access token in an httpOnly cookie with a 15 minute lifetime. CSRF token is a double submit cookie read by the frontend and echoed in the X-CSRF-Token header on state changing requests.
- Money is sent to the frontend as strings where practical, but integer minor units are also acceptable for small calculations; frontend uses Decimal.js for EMI and financing comparisons.
- The forecast engine treats incoming receivables as paid on the due date plus the counterparty's average historical delay. A 14 day default delay is applied when no counterparty profile exists.
- The financing matcher labels all seeded products as example terms. Real lenders are not inventoried; the user edits the catalog in Settings.
- Forgotten password flow is only exposed when SMTP is configured; otherwise the link is hidden in the UI.
- Persisted permissions are simple: owner, finance, viewer. Org scoped authorization is enforced on every router.
- FX rates come from the Frankfurter API (ECB reference). In offline mode the last stored rate or the shipped static file is used.
- LLM content is always masked before any prompt reaches the model. Tokens are replaced only at render time in the UI.
- Legal pages use tokens such as {{LEGAL_ENTITY}} read from legal.config.ts. Those must be filled before launch.
