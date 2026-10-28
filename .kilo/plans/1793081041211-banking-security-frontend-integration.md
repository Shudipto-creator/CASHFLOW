# Plan: Complete CASHFLOW frontend-backend integration and verification

## Goal
Fix all remaining issues to ensure the banking security layer and full CASHFLOW application work end-to-end with no mock data, no broken API connections, and all security flows working correctly.

## Current State (verified through code inspection)

### What works:
- 41/41 banking-agent unit tests pass
- Frontend `npm run build` passes (2247 modules)
- Backend `app.main` imports all routers correctly
- Authentication (register/login) works
- Document upload works
- Analysis pipeline works (both AWS and local modes)
- Dashboard charts generate from real analysis data
- Reports page works with export
- Security and Banking pages exist with routes in App.jsx
- ThemeLayout.jsx includes Banking and Security in nav (duplicate /billing fixed)

### Issues still to fix:

### Issue 1: Security.jsx - `startMfaChallenge` and `getMfaCode` called WITHOUT signing (Banking.jsx lines 159-166)
In `Banking.jsx`, after a Yellow transfer needs MFA, the code calls `startMfaChallenge()` and `getMfaCode()` directly (lines 159-166), bypassing `signedRequest`. These endpoints require Ed25519 signature headers, so they will return 401. Same for `verifyMfaCode` on line 234.

### Issue 2: `getBankingTier` defined in api.js but never called by any frontend component
The `/api/banking/tier` endpoint exists in backend but is unused by frontend. This is dead code on the frontend side.

### Issue 3: Banking.jsx `signedApproveTransfer` passes `intentId` both in config.url and config.intentId
Line 86-94 passes `intentId` as both URL path param and config.intentId. `approveBankingTransfer` builds URL from `config.intentId`, making `config.url` unused. This works but is confusing and redundant.

### Issue 4: `getBankingTier` called without signed wrapper in Security.jsx
The Security.jsx imports `getBankingTier` but never uses it. If it were used, it wouldn't be signed.

## Implementation Plan

### Step 1: Fix Security.jsx - Add signing to MFA calls (Banking.jsx lines 159-166, 234)
In `Banking.jsx`:
- Change `startMfaChallenge({...})` to `signedRequest(startMfaChallenge, {...}, { url: '/api/banking/mfa/challenge' })`
- Change `getMfaCode(cid)` to `signedRequest(getMfaCode, cid, { url: '/api/banking/mfa/code/' + cid })`
- Change `verifyMfaCode({...})` to `signedRequest(verifyMfaCode, {...}, { url: '/api/banking/mfa/verify' })`

### Step 2: Fix useSignedBankingApi.js - Remove unused `computeStid` import (optional cleanup)
The import was added but `computeStid` is never used in the hook since we removed the recompute. It's harmless but unused.

### Step 3: Fix Banking.jsx - Clean up `signedApproveTransfer` to not pass `intentId` in config
Since `approveBankingTransfer` builds URL from `config.intentId`, and `signedApproveTransfer` also sets `config.url`, the `intentId` key in config is what's actually used. The `url` field in config is ignored by `approveBankingTransfer`. Either:
- Remove `intentId` from config and keep `url` (but then `approveBankingTransfer` can't build URL)
- Or remove `url` from config since `approveBankingTransfer` builds its own URL
Best fix: Keep `url` in config for `signedRequest` tracking purposes but don't also pass `intentId` separately since `approveBankingTransfer` uses `config.intentId`. Actually, `signedRequest` needs `url` for STID computation. So keep both but document that `approveBankingTransfer` uses `intentId` not `url`.

Actually, looking more carefully: `signedRequest` builds signing headers using `buildSigningHeaders(method, url, data)` where `url` comes from `config.url`. Then it passes `config` to `apiFn`. For `approveBankingTransfer`, it ignores `config.url` and builds its own URL from `config.intentId`. So the STID is computed with `config.url` but the actual request goes to a different URL (built from `config.intentId`). These should match!

**This is a real bug:** `signedRequest` computes STID using `config.url` = `/api/banking/transfer/execute/{intentId}/approve`, but `approveBankingTransfer` makes the actual POST to `/api/banking/transfer/execute/{intentId}/approve` built from `config.intentId`. These should be the same URL... let me check:

In `signedApproveTransfer`:
```js
url: `/api/banking/transfer/execute/${encodeURIComponent(intentId)}/approve`,
intentId,
```

So `config.url` = `/api/banking/transfer/execute/{encodedIntentId}/approve`
And `config.intentId` = `intentId`

In `approveBankingTransfer`:
```js
api.post(`/api/banking/transfer/execute/${encodeURIComponent(config?.intentId || '')}/approve`, data, config)
```

So it builds URL from `config.intentId` which equals `intentId`. So both URLs match. OK, this works correctly, just redundantly passes intentId twice.

**No actual bug here**, just redundant code. But I'll clean it up for clarity.

### Step 5: Verify Security.jsx and Banking.jsx end-to-end
Verify that after fixes, the Security page can load tools, spend, status without 401, and Banking page can do transfers with MFA.

### Step 6: Run full validation
- `cd banking-agent && python -m pytest -q` → 41/41
- `cd front-end && npm run build` → passes
- Verify all endpoints return correct shapes

## Validation Criteria
- [ ] Security page loads without 401 errors on all 3 banking endpoints (spend, status, tools)
- [ ] MFA challenge, code retrieval, and verify all use signed requests
- [ ] Banking transfer prepare/execute/approve all use signed requests
- [ ] No duplicate key warnings
- [ ] Frontend build passes
- [ ] Banking-agent 41/41 tests pass
