from functools import lru_cache
import logging
import secrets
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
logger = logging.getLogger("careersense")

INSECURE_SECRET_KEYS = frozenset(
    {
        "",
        "change-me-in-production",
        "careersense-local-dev-only-change-me",
        "changeme",
        "secret",
        "secret-key",
    }
)

PLACEHOLDER_EMAIL_API_KEYS = frozenset(
    {
        "re_your_key",
        "your-key",
        "changeme",
        "change-me",
        "api-key",
        "email_api_key",
    }
)


def looks_like_placeholder_email_key(value: str) -> bool:
    raw = (value or "").strip().lower()
    if not raw:
        return True
    if raw in PLACEHOLDER_EMAIL_API_KEYS:
        return True
    return "your_key" in raw or "your-key" in raw


def looks_like_placeholder_from_address(value: str) -> bool:
    raw = (value or "").strip().lower()
    if not raw or "@" not in raw:
        return True
    # Resend free/onboarding sender used when no custom domain is verified.
    if raw.endswith("@resend.dev"):
        return False
    if "your-verified-domain" in raw or "yourdomain" in raw:
        return True
    return raw.endswith("@example.com")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CareerSense"
    environment: str = "development"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'careersense.db').as_posix()}"
    secret_key: str = ""
    access_token_expire_minutes: int = 720
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    upload_dir: str = "uploads"
    max_upload_mb: int = 10
    enable_docs: Optional[bool] = None
    rate_limit_enabled: bool = True
    trust_x_forwarded_for: bool = False
    oaaps_office_name: str = "Office of Alumni Affairs and Placement Services"
    oaaps_email: str = ""
    oaaps_phone: str = ""
    oaaps_hours: str = ""
    oaaps_location: str = "Angeles University Foundation"
    public_app_url: str = "http://localhost:5173"
    frontend_url: str = ""
    email_enabled: Optional[bool] = None
    email_provider: str = ""
    email_api_key: str = ""
    email_from_address: str = ""
    email_from_name: str = "CareerSense"
    email_reply_to: str = ""
    email_base_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    smtp_timeout_seconds: int = 15
    email_retry_attempts: int = 3
    email_retry_backoff_ms: int = 400
    email_outbox_max_attempts: int = 5
    email_scheduler_enabled: Optional[bool] = None
    email_scheduler_interval_seconds: int = 60
    email_timezone: str = "Asia/Manila"

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"production", "prod"}

    @property
    def docs_enabled(self) -> bool:
        if self.enable_docs is not None:
            return self.enable_docs
        return not self.is_production

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        extra = (self.frontend_url or "").strip().rstrip("/")
        if extra and extra not in origins:
            origins.append(extra)
        return origins

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolved_email_from(self) -> str:
        return (self.email_from_address or self.smtp_from or self.smtp_username or "").strip()

    def resolved_email_provider(self) -> str:
        raw = (self.email_provider or "").strip().lower()
        if raw in {"resend", "smtp"}:
            return raw
        if (self.email_api_key or "").strip():
            return "resend"
        if (self.smtp_host or "").strip():
            return "smtp"
        return ""

    def email_provider_ready(self) -> bool:
        sender = self.resolved_email_from()
        if looks_like_placeholder_from_address(sender):
            return False
        name = self.resolved_email_provider()
        if name == "resend":
            key = (self.email_api_key or "").strip()
            return bool(key) and not looks_like_placeholder_email_key(key)
        if name == "smtp":
            return bool((self.smtp_host or "").strip())
        return False

    def validate_email_configuration(self) -> None:
        enabled = self.email_enabled is True or (self.email_enabled is None and self.is_production)
        if self.is_production and self.email_enabled is False:
            raise RuntimeError(
                "EMAIL_ENABLED cannot be false when ENVIRONMENT=production. "
                "CareerSense must send transactional email through Resend."
            )
        if not enabled and self.email_enabled is not True:
            return
        if self.email_enabled is True or self.is_production:
            provider = self.resolved_email_provider()
            if provider != "resend":
                raise RuntimeError(
                    "EMAIL_PROVIDER must be 'resend' when EMAIL_ENABLED=true. "
                    "See docs/resend-email.md."
                )
            if looks_like_placeholder_from_address(self.resolved_email_from()):
                raise RuntimeError(
                    "EMAIL_FROM_ADDRESS must be a real verified sender, not a placeholder. "
                    "Use a Resend onboarding address such as beth.t@example.com for tests, "
                    "or a verified domain address in production. See docs/resend-email.md."
                )
            key = (self.email_api_key or "").strip()
            if looks_like_placeholder_email_key(key):
                raise RuntimeError(
                    "EMAIL_API_KEY must be a real Resend API key when EMAIL_ENABLED=true. "
                    "Do not use re_your_key. See docs/resend-email.md."
                )
            if not (self.email_base_url or self.public_app_url or "").strip():
                raise RuntimeError("EMAIL_BASE_URL or PUBLIC_APP_URL must be set when EMAIL_ENABLED=true.")

    def prepare(self) -> "Settings":
        key = (self.secret_key or "").strip()
        insecure = key.lower() in INSECURE_SECRET_KEYS or len(key) < 16
        if self.is_production:
            if insecure or len(key) < 32:
                raise RuntimeError(
                    "SECRET_KEY must be set to a unique value of at least 32 characters "
                    "when ENVIRONMENT=production. Do not use the example value from .env.example."
                )
            if self.database_url.strip().lower().startswith("sqlite"):
                raise RuntimeError(
                    "DATABASE_URL must be a PostgreSQL URL when ENVIRONMENT=production. "
                    "SQLite files do not persist on Render."
                )
            origins = self.cors_origin_list
            if not origins or any(item == "*" for item in origins):
                raise RuntimeError(
                    "Set CORS_ORIGINS or FRONTEND_URL to the explicit frontend origin when "
                    "ENVIRONMENT=production. Wildcard origins are not allowed."
                )
            self.secret_key = key
            self.validate_email_configuration()
            return self
        if not key:
            self.secret_key = secrets.token_urlsafe(48)
            logger.warning(
                "SECRET_KEY is missing. Generated an ephemeral development key; "
                "sessions will not survive process restart. Set SECRET_KEY in backend/.env."
            )
        elif insecure:
            logger.warning(
                "SECRET_KEY is an insecure example value. This is allowed only in development. "
                "Set a unique SECRET_KEY before any campus deployment."
            )
        self.validate_email_configuration()
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings().prepare()
