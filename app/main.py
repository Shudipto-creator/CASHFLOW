"""CASHFLOW FastAPI application: middleware, error pages, routers."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings, is_production
from app.db import engine, init_db, get_db
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.templating import render

settings = get_settings()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

class _SafeFormatter(logging.Formatter):
    def formatMessage(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return super().formatMessage(record)


_log_format = '{"timestamp":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","request_id":"%(request_id)s","message":"%(message)s"}'
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format=_log_format,
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    force=True,
)
for _handler in logging.getLogger().handlers:
    _handler.setFormatter(_SafeFormatter(_log_format, datefmt="%Y-%m-%dT%H:%M:%SZ"))
logger = logging.getLogger("cashflow")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting CASHFLOW application", extra={"request_id": "bootstrap"})
    init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down CASHFLOW application")


app = FastAPI(
    title="CASHFLOW",
    description="Cash flow copilot for SMEs",
    version="1.0.0",
    docs_url=None if is_production() else "/docs",
    redoc_url=None if is_production() else "/redoc",
    lifespan=lifespan,
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = int((time.time() - start) * 1000)
    logger.info(
        "%s %s -> %s in %dms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        extra={"request_id": _request_id(request)},
    )
    return response


# Import routers after app creation to avoid circular imports.
from app.routers import (  # noqa: E402
    public,
    auth,
    accounts,
    analysis,
    approvals,
    ask_cfo,
    audit,
    counterparts,
    dashboard,
    documents,
    financing,
    forecasts,
    goals,
    invoices,
    organizations,
    settings as settings_router,
    support,
    transactions,
)

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(analysis.router)
app.include_router(approvals.router)
app.include_router(ask_cfo.router)
app.include_router(audit.router)
app.include_router(counterparts.router)
app.include_router(dashboard.router)
app.include_router(documents.router)
app.include_router(financing.router)
app.include_router(forecasts.router)
app.include_router(goals.router)
app.include_router(invoices.router)
app.include_router(organizations.router)
app.include_router(settings_router.router)
app.include_router(support.router)
app.include_router(transactions.router)


@app.get("/healthz")
async def healthz():
    from sqlalchemy import text

    with next(get_db()) as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok", "version": "1.0.0"}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return render(request, "errors/404.html", title="Page not found", status_code=404)
    if exc.status_code == 403:
        return render(request, "errors/403.html", title="Forbidden", status_code=403)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled error: %r", exc, extra={"request_id": _request_id(request)}, exc_info=True
    )
    return render(request, "errors/500.html", title="Server error", status_code=500)
