# Plan: Fix CASHFLOW unstyled page ("only showing texts")

## Problem
The CASHFLOW app serves HTML pages (200 OK) and static assets (CSS/JS/fonts all return 200 via direct HTTP test), but the rendered page shows unstyled text only — CSS styles are not being applied in the browser.

## Root Causes to Investigate

1. **Content-Type with `nosniff`**: `SecurityHeadersMiddleware` sets `X-Content-Type-Options: nosniff`. If Starlette's `StaticFiles` serves `.css` files with a non-`text/css` Content-Type, browsers will refuse to apply the stylesheet.
2. **CSP violation**: CSP `style-src 'self'` is set. Same-origin `/static/css/*.css` should be allowed, but need to verify no inline styles or `unsafe-inline` issues block rendering.
3. **Browser cache**: User may have a cached HTML page without CSS links.
4. **CSS file linking order**: `tokens.css` (defines CSS custom properties) is loaded first in both base templates, which is correct.

## Already Completed (verified working)

- Server runs on `http://127.0.0.1:8002` (PID managed by background process)
- All HTML routes: `/`, `/healthz`, `/login`, `/register` → 200; `/app/*` → 401 (correct, unauthenticated)
- All static assets: 6 CSS files, 4 JS files, fonts, icons, favicon → all 200
- `/static` mount added in `app/main.py:70`
- Favicon path fixed from `favicon.svg` to `img/favicon.svg` in both base templates
- Logging formatter crash fixed with `_SafeFormatter` in `app/main.py`
- Old `app/.env` with hardcoded AWS credentials removed
- Black formatting applied to all new/modified Python files

## Remaining Tasks

### 1. Verify Content-Type headers for static files
Check that `StaticFiles` serves `.css` as `text/css`, `.js` as `application/javascript`, `.woff2` as `font/woff2`. If wrong, configure explicit media types.

### 2. Check browser console for CSP violations
Load `http://127.0.0.1:8002/` in a browser and check DevTools Console/Network for:
- CSP violations blocking stylesheets
- Failed resource loads (404, 403, MIME type errors)
- CSS parse errors

### 3. Fix any Content-Type or CSP issues found
If `StaticFiles` serves wrong Content-Type, add explicit media type mapping. If CSP blocks styles, adjust the policy in `app/middleware/security_headers.py`.

### 4. Restart server and verify end-to-end
Restart uvicorn, load all routes in browser, confirm CSS is applied (colors, layout, fonts visible).

## Validation

- `GET /` → 200 with styled landing page (not plain text)
- `GET /login` → 200 with styled login form
- `GET /register` → 200 with styled register form
- All `/static/css/*.css` → 200 with `Content-Type: text/css`
- Browser console shows no CSP violations or MIME type errors
- `GET /healthz` → 200

## Files Involved

- `app/main.py` — static mount, logging fix (already applied)
- `app/middleware/security_headers.py` — CSP policy (may need adjustment)
- `app/templates/base_public.html`, `base_app.html` — CSS/JS linking (already fixed favicon)
- `app/static/css/` — all 6 CSS files (verified present and serving)

## Open Question

Does the user see plain unstyled text in a specific browser? Chrome/Firefox/Safari may handle CSP/MIME differently. Need browser confirmation before finalizing any CSP changes.