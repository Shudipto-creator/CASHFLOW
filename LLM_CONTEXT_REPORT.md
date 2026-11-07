# FINN CFO conversation memory — implementation report

Date: 2026-11-07

## 1. Architecture verified first

CASHFLOW uses two separate SQLite databases:

| Database | Role | What it contains |
| --- | --- | --- |
| `data/finndb.sqlite` | Sandbox core-banking database (FINNDB) | 10 customers `CUS001`–`CUS010`; 12 accounts `ACC001`–`ACC012` (each customer has a PRIMARY account, plus joint `ACC011` for `CUS001`/`CUS002`, plus a second account `ACC012` for `CUS005`); all accounts ACTIVE and CNY; `account_holders`, `account_transactions`, transfer intents |
| `data/cfone.db` | Application database | users, password hashes, analyses, documents, FINN contacts, `bank_customer_links`, and now `cfo_chat_messages` |

The bridge between the two is `app/services/finn_bank.py`:

- `customer_id_for(user)` matches the app user's `company_name` against `customers.legal_name` in FINNDB. If there is no match it assigns the first unassigned customer and stores an exclusive row in `bank_customer_links`. Linking is lazy (on first bank access), not on registration.
- Only the 10 pre-seeded customers exist, so the 11th distinct user cannot be linked and receives HTTP 409. The existing `cfone.db` has 40 users but only 4 links because most users have never touched the bank.
- `accounts_for(user)` returns only accounts where the linked customer appears in `account_holders`.
- `transactions_for(user)` and `transaction_totals_for(user, ...)` join `account_holders` by `customer_id`, so a user sees their own accounts and any joint account they hold, never another customer's ledger rows.

This is the behaviour requested: the username/company name resolves the FINN customer, and transactions are filtered by the account holders linked to that customer.

Before this change, the main CFO chat (`POST /api/banking/agent/chat`, used by `CfoChatPage.jsx`) received only the newest message. The transcript lived only in browser `localStorage`, and `interpret_cfo_intent` got a single sentence. As a result the model could not resolve follow-ups such as “and last month?” or “上个月呢？” and out-of-scope questions could fall through to a raw `NOT_IMPLEMENTED` operation dump.

## 2. What changed

### Durable server-side transcript

- `app/models.py`: new `CfoChatMessage` table (`cfo_chat_messages`) with `conversation_id`, `user_id`, `role`, `content`, `intent`, `message_metadata`, `created_at`.
- `app/services/cfo_conversation.py` (new): conversation-id normalisation, language detection, follow-up detection, period extraction, append/load/delete history, last-topic helpers and prompt formatting.
- `app/routers/banking_agent.py`: every chat turn now loads the user's history before routing and persists both the user message and the assistant reply. History is scoped by `user_id` AND `conversation_id`; a conversation id from another user returns nothing.
- `app/database.py` / startup already calls `init_db()`, which creates the new table. It was also created in the current `data/cfone.db` during verification.

### History reaches the model

- `app/services/cfo_intent.py`: accepts `history` and `language`, injects a `CONVERSATION SO FAR` block, and adds explicit context/follow-up/out-of-scope/language rules.
- `app/services/ollama_client.py` and `app/services/nova_client.py`: support `json_mode`; the intent interpreter and operation selector request JSON output, which makes the local `llama3.2` model far more reliable.
- `app/services/llm_banking_agent.py`: `DeterministicSelector`, `LLMSelector` and `LLMBankingAgent.handle` pass conversation history into operation selection.

### Follow-ups resolve deterministically

Short follow-ups no longer depend on the model guessing:

- “and last month?” / “上个月呢？” after a spending or income summary inherits the previous direction and period.
- A follow-up after a balance question keeps the balance topic.
- A transfer follow-up keeps the previous recipient context.
- English and Chinese period phrases (“this month”, “last month”, “this year”, “这个月”, “上个月”, “今年”) are parsed locally.

### Localized, safe answers

The chat now has deterministic English/Chinese replies for:

- balance and account lists (local currency formatting, account suffix),
- income/spending summaries,
- greetings (“Hello” / “你好”),
- out-of-scope questions (a helpful FINN-only answer instead of a registry dump),
- transfer prompts and errors.

A final language guard (`_reply_in_language`) checks the model's prose against the user's language. If the small model answers in the wrong language, the localized fallback is used instead. This was added after the live test produced a Chinese reply to an English message.

### Frontend

- `web-app/src/services/api.js`: `getCfoConversation(token, conversationId)`.
- `web-app/src/pages/CfoChatPage.jsx`: keeps a per-user conversation id in `localStorage`, sends `conversation_id` with normal and confirmed-transfer turns, stores the returned id, and restores the server transcript when local history is empty. Local storage remains the offline fallback and still holds pending transfer actions.

### Ask-CFO

`app/routers/ask_cfo.py` now has the same language rules, a Chinese/English greeting path, and a larger history window (24 stored messages, 12 in the prompt).

### Configuration

`app/config.py` now defaults to `sqlite:///./data/cfone.db`, matching `.env.example` and the populated app database. Previously the default pointed at a non-existent `data/cashflow.db`.

## 3. API changes

`POST /api/banking/agent/chat` request adds:

- `conversation_id` (optional; generated if omitted)
- `language` (optional; detected from the message when omitted)

Response adds:

- `conversation_id`
- `language`

New endpoints:

- `GET /api/banking/agent/chat/history?conversation_id=...&limit=...`
- `DELETE /api/banking/agent/chat/history?conversation_id=...`

Both require authentication and are scoped to the current user.

## 4. Verification actually run

### Automated tests

```bash
python -m pytest tests/test_cfo_conversation.py \
  tests/test_banking_agent_balance.py \
  tests/test_auth_recovery.py \
  tests/test_contacts_transfers.py -q
```

Result: **51 passed** (13 new conversation tests + 31 existing balance/auth + 7 contacts/transfer tests).

The new tests cover:

- persistence of both roles and the returned conversation id,
- history isolation between two users sharing a conversation id,
- durable history reaching the intent interpreter,
- English follow-up inheriting spending direction and previous month,
- Chinese balance and spending replies,
- Chinese “上个月呢？” follow-up,
- English and Chinese out-of-scope answers,
- English and Chinese greetings without an LLM call,
- language-guard replacement of wrong-language model prose,
- FINN account/transaction isolation: Li Wei (`ACC001` + joint `ACC011`) vs Wang Fang (`ACC002` + joint `ACC011`).

### Frontend

```bash
cd web-app
npm ci
npm run build
```

Result: Vite production build succeeded (`1377 modules transformed`).

### Live local model

```bash
PYTHONIOENCODING=utf-8 python scripts/verify_cfo_llm.py
```

The script uses a temporary app database, the real `data/finndb.sqlite`, and the configured local Ollama model (`llama3.2`). Selected actual responses:

- **English balance** (`What is my balance?`) → `OK`, `get-accounts`; total `CNY 81,000.00` across accounts ending 0001 and 0011.
- **English out-of-scope** (`Can you recommend the best pizza in Rome?`) → `OUT_OF_SCOPE`; polite English reply, no invented bank data.
- **Chinese balance** (`我的账户余额是多少？`) → `OK`, `get-accounts`; `您的可用余额：... CNY 可用总额：81,000.00。`
- **Chinese out-of-scope** (`给我推荐一部好看的电影。`) → `OUT_OF_SCOPE`; Chinese reply explaining it can only help with FINN accounts/transactions/transfers.
- **English spending** → `¥1,268.50 across 2 transaction(s)` for `2026-11-01` to `2026-11-07`.
- **English follow-up** (`and last month?`) → correct `2026-10-01` to `2026-10-31`, same topic, no LLM needed.
- **Chinese spending** → `¥1,268.50，共 2 笔交易`.
- **Chinese follow-up** (`上个月呢？`) → correct previous-month range in Chinese.
- **Context turn** (`I run a small bakery in Shanghai.`) → English reply after the language guard.
- Final transcript: **20 stored messages** for 10 turns, confirming both sides of every turn are durable.

## 5. Known limits

- The local `llama3.2` 3B model is usable but not perfect; the language guard and deterministic routes exist to contain its weaker outputs.
- Linking is capped by the 10 seeded FINN customers. A new user beyond that receives a clear 409 rather than a fabricated account.
- `python-telegram-bot` and `wecom-aibot-python-sdk` are optional; the app disables those channels when they or their tokens are absent.
- The live check prints Chinese, so the script forces UTF-8 on Windows consoles.

## 6. requirements.txt

`requirements.txt` now also lists the banking-gate packages (`bank2ai==0.6.1`, `fastmcp==4.1.3`) and the two optional IM SDKs. If a particular environment reports a `fastapi`/`fastmcp`/starlette conflict, the gate packages can be installed in `banking-agent/.venv` as described in `requirements-smart-transfer.txt`.
