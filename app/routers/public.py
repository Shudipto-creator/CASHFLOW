"""Public HTML page routes for CASHFLOW.

Server-rendered pages for the marketing site and the authenticated app shell.
All routes return HTML via Jinja2 templates; API endpoints live in the other
routers under the /api prefix.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse

from app.templating import render
from app.dependencies import get_optional_user, get_current_user

router = APIRouter(tags=["public"])


# ---------------------------------------------------------------------------
# Public (marketing) pages
# ---------------------------------------------------------------------------


@router.get("/", name="landing")
async def landing(request: Request, user=Depends(get_optional_user)):
    """Landing page. Redirects authenticated users to the app dashboard."""
    if user:
        return RedirectResponse(url="/app", status_code=status.HTTP_302_FOUND)
    return render(request, "public/landing.html", title="CASHFLOW — Cash flow copilot for SMEs")


@router.get("/login", name="login")
async def login_page(request: Request, user=Depends(get_optional_user)):
    """Login page."""
    if user:
        return RedirectResponse(url="/app", status_code=status.HTTP_302_FOUND)
    return render(request, "public/login.html", title="Sign in — CASHFLOW")


@router.get("/register", name="register")
async def register_page(request: Request, user=Depends(get_optional_user)):
    """Register page."""
    if user:
        return RedirectResponse(url="/app", status_code=status.HTTP_302_FOUND)
    return render(request, "public/register.html", title="Create account — CASHFLOW")


# ---------------------------------------------------------------------------
# App (authenticated) pages
# ---------------------------------------------------------------------------


@router.get("/app", name="app_dashboard")
async def app_dashboard(request: Request, user=Depends(get_current_user)):
    """App shell dashboard."""
    return render(
        request,
        "app/dashboard.html",
        title="Dashboard — CASHFLOW",
        user_email=user.email,
    )


@router.get("/app/forecasts", name="app_forecasts")
async def app_forecasts(request: Request, user=Depends(get_current_user)):
    """Forecasts page."""
    return render(
        request,
        "app/forecasts.html",
        title="Forecasts — CASHFLOW",
    )


@router.get("/app/documents", name="app_documents")
async def app_documents(request: Request, user=Depends(get_current_user)):
    """Documents page."""
    return render(
        request,
        "app/documents.html",
        title="Documents — CASHFLOW",
    )


@router.get("/app/ask", name="app_ask")
async def app_ask(request: Request, user=Depends(get_current_user)):
    """Ask CASHFLOW chat page."""
    return render(
        request,
        "app/ask.html",
        title="Ask CASHFLOW — CASHFLOW",
    )


@router.get("/app/settings", name="app_settings")
async def app_settings(request: Request, user=Depends(get_current_user)):
    """Settings page."""
    return render(
        request,
        "app/settings.html",
        title="Settings — CASHFLOW",
    )
