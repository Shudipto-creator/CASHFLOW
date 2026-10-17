"""Middleware setup for CASHFLOW."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.config import get_settings

settings = get_settings()


def setup_middleware(app: FastAPI) -> None:
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", settings.csrf_header_name, "X-Request-Id"],
        expose_headers=["X-Request-Id"],
        max_age=600,
    )
