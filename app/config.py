"""Application configuration for CASHFLOW.

All settings come from environment variables, read once here and validated at
startup. The app refuses to start with a clear message when a required value is
missing or malformed (see config.validate()).
"""

from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import List

from cryptography.fernet import Fernet
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), case_sensitive=False, extra="ignore"
    )

    # --- Application ---
    app_name: str = Field(default="CASHFLOW")
    app_env: str = Field(default="development")  # development | production
    debug: bool = Field(default=False)
    secret_key: str = Field(default="")
    site_url: str = Field(default="http://localhost:8000")
    asset_version: str = Field(default="dev")
    log_level: str = Field(default="INFO")

    # --- Database ---
    database_url: str = Field(default="sqlite:///./data/cashflow.db")

    # --- Sessions / cookies ---
    cookie_secure: bool = Field(default=False)
    session_cookie_name: str = Field(default="cf_session")
    refresh_cookie_name: str = Field(default="cf_refresh")
    csrf_cookie_name: str = Field(default="cf_csrf")
    session_idle_days_signed_in: int = Field(default=14)
    session_absolute_days_signed_in: int = Field(default=30)
    session_idle_hours_guest: int = Field(default=24)
    session_absolute_days_guest: int = Field(default=7)

    # --- Field encryption ---
    field_encryption_key: str = Field(default="")

    # --- Auth ---
    bcrypt_rounds: int = Field(default=12)
    password_min_length: int = Field(default=12)
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_expire_minutes: int = Field(default=15)
    jwt_refresh_expire_days: int = Field(default=30)
    login_rate_limit_per_minute: int = Field(default=5)
    login_backoff_seconds: int = Field(default=30)
    signup_rate_limit_per_hour: int = Field(default=10)
    password_reset_rate_limit_per_hour: int = Field(default=5)

    # --- Guest mode ---
    guest_max_active: int = Field(default=500)
    guest_start_rate_limit_per_ip_per_day: int = Field(default=5)
    guest_upload_max_mb: int = Field(default=2)
    guest_upload_max_rows: int = Field(default=5000)
    guest_model_requests_per_day: int = Field(default=20)

    # --- LLM ---
    llm_provider: str = Field(default="mock")
    llm_model: str = Field(default="mock-model")
    llm_base_url: str = Field(default="")
    llm_api_key: str = Field(default="")
    llm_timeout_seconds: int = Field(default=30)
    llm_daily_budget_per_org: int = Field(default=100)

    # --- FX ---
    frankfurter_base_url: str = Field(default="https://api.frankfurter.app")
    fx_fallback_file: str = Field(default="app/data/fx_fallback.json")

    # --- Uploads ---
    upload_dir: str = Field(default="./uploads")
    max_upload_size_mb: int = Field(default=20)
    document_max_size_mb: int = Field(default=20)
    screenshot_max_size_mb: int = Field(default=5)
    xlsx_max_uncompressed_mb: int = Field(default=100)

    # --- Email / SMTP ---
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from: str = Field(default="")
    smtp_tls: bool = Field(default=True)

    # --- Support / legal ---
    support_email: str = Field(default="support@localhost")
    security_email: str = Field(default="security@localhost")

    # --- Scheduler ---
    alert_interval_hours: int = Field(default=6)

    # --- Site facts (content/site.json is the source; these are convenience) ---
    legal_entity: str = Field(default="REPLACE_ME")
    contact_email: str = Field(default="REPLACE_ME")
    governing_law: str = Field(default="REPLACE_ME")
    hosting_provider: str = Field(default="REPLACE_ME")
    llm_provider_name: str = Field(default="REPLACE_ME")

    @field_validator("secret_key")
    @classmethod
    def _check_secret_key(cls, v: str) -> str:
        if not v:
            raise ValueError("SECRET_KEY is required")
        import base64

        try:
            raw = base64.b64decode(v, validate=True)
        except Exception as exc:
            raise ValueError("SECRET_KEY must be base64 encoded") from exc
        if len(raw) < 32:
            raise ValueError("SECRET_KEY must decode to at least 32 random bytes")
        return v

    @field_validator("field_encryption_key")
    @classmethod
    def _check_field_encryption_key(cls, v: str) -> str:
        if not v:
            raise ValueError("FIELD_ENCRYPTION_KEY is required")
        for key in [k.strip() for k in v.split(",") if k.strip()]:
            try:
                Fernet(key.encode())
            except Exception as exc:
                raise ValueError(
                    f"FIELD_ENCRYPTION_KEY contains an invalid Fernet key: {key}"
                ) from exc
        return v

    @field_validator("database_url")
    @classmethod
    def _check_database_url(cls, v: str) -> str:
        if not v:
            raise ValueError("DATABASE_URL is required")
        if not (
            v.startswith("sqlite:///") or v.startswith("postgresql+") or v.startswith("postgres+")
        ):
            raise ValueError("DATABASE_URL must be sqlite:/// or postgresql+...")
        return v

    @field_validator("site_url")
    @classmethod
    def _check_site_url(cls, v: str) -> str:
        if not v:
            raise ValueError("SITE_URL is required")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("SITE_URL must start with http:// or https://")
        return v.rstrip("/")

    @field_validator("llm_provider")
    @classmethod
    def _check_llm_provider(cls, v: str) -> str:
        if v not in ("mock", "bedrock", "openai_compatible"):
            raise ValueError("LLM_PROVIDER must be mock, bedrock or openai_compatible")
        return v

    @model_validator(mode="after")
    def _check_production_required(self) -> "Settings":
        if self.app_env == "production":
            missing: List[str] = []
            for name in (
                "site_url",
                "secret_key",
                "field_encryption_key",
                "database_url",
                "support_email",
                "security_email",
            ):
                value = getattr(self, name)
                if not value or value == "REPLACE_ME":
                    missing.append(name.upper())
            if missing:
                raise ValueError("Missing required production settings: " + ", ".join(missing))
        return self

    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password and self.smtp_from)

    def encryption_keys(self) -> List[str]:
        return [k.strip() for k in self.field_encryption_key.split(",") if k.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def generate_secret_key() -> str:
    import base64

    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


def generate_fernet_key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode("ascii")


def is_production(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return s.app_env == "production"
