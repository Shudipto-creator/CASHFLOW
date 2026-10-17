"""Template rendering helper with common context (section 8.4)."""

from __future__ import annotations

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import get_settings, is_production

settings = get_settings()
BASE_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def static(path: str) -> str:
    return f"/static/{path}?v={settings.asset_version}"


templates.env.globals["static"] = static


def _flash(request: Request):
    """Pop one flash message from the session cookie (stored as __cf_flash)."""
    data = request.cookies.get("__cf_flash")
    if not data:
        return None
    import base64, json

    try:
        msg = json.loads(base64.b64decode(data).decode("utf-8"))
    except Exception:
        return None
    return msg


def _cookie_name() -> str:
    return "__Host-cf_session" if settings.cookie_secure else "cf_session"


def render(request: Request, template: str, status_code: int = 200, **extra):
    """Render a template with the standard CASHFLOW context."""
    session_token = request.cookies.get(_cookie_name())
    context = {
        "request": request,
        "settings": settings,
        "site_url": settings.site_url,
        "asset_version": settings.asset_version,
        "is_production": is_production(),
        "flash": _flash(request),
        "session_token": session_token,
        "csrf_token": None,
    }
    if session_token:
        # csrf token supplied by the caller via extra.get("csrf_token")
        pass
    context.update(extra)
    from fastapi.responses import HTMLResponse

    content = templates.TemplateResponse(template, context)
    if isinstance(content, HTMLResponse):
        content.status_code = status_code
    return content
