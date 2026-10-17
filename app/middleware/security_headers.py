"""Security headers middleware (section 13.5)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import get_settings

settings = get_settings()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        is_app = request.url.path.startswith("/app/")
        is_public_html = request.url.path.startswith("/") and not request.url.path.startswith(("/static/", "/api/"))
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self'; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "object-src 'none'"
        )
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Caching
        if is_app:
            response.headers["Cache-Control"] = "no-store"
        elif request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif is_public_html:
            response.headers["Cache-Control"] = "public, max-age=300"
        # App routes are not indexed
        if is_app:
            response.headers["X-Robots-Tag"] = "noindex"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
