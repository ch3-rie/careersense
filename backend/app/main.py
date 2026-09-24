import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import BACKEND_DIR, get_settings
from app.db import SessionLocal, ensure_runtime_schema
from app.routers import admin, admin_cards, admin_perks, admin_profile_reminders, admin_profile_updates, admin_survey, admin_users, alumni, auth
from app.seed import seed_if_empty
from app.services.email import email_health, scheduler_is_enabled

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("careersense")
settings = get_settings()


def _run_alembic() -> None:
    try:
        from alembic import command
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        from app.db import engine

        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        cfg.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
        cfg.attributes["configure_logger"] = False
        script = ScriptDirectory.from_config(cfg)
        head = script.get_current_head()
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
        if current == head:
            logger.info("Database schema is current (%s)", current)
            return
        command.upgrade(cfg, "head")
    except Exception as exc:
        if settings.is_production:
            logger.exception("Alembic upgrade failed in production")
            raise RuntimeError(f"Alembic upgrade failed: {exc}") from exc
        logger.warning("Alembic upgrade did not run (%s). Applying runtime schema checks instead.", exc)
        ensure_runtime_schema()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_runtime_schema()
    _run_alembic()
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    stop = None
    task = None
    if scheduler_is_enabled():
        import asyncio

        from app.services.email.scheduler import run_email_scheduler

        stop = asyncio.Event()
        task = asyncio.create_task(run_email_scheduler(stop))
        logger.info("Email scheduler task created")
    try:
        yield
    finally:
        if stop is not None:
            stop.set()
        if task is not None:
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=5)
            except BaseException:
                pass


docs_url = "/docs" if settings.docs_enabled else None
redoc_url = "/redoc" if settings.docs_enabled else None
openapi_url = "/openapi.json" if settings.docs_enabled else None

app = FastAPI(
    title="CareerSense API",
    description="AUF Office of Alumni Affairs and Placement Services — Graduate Tracer System",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SecurityHeadersMiddleware:
    """Pure ASGI wrapper so headers are applied on the live Uvicorn stack."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=message.setdefault("headers", []))
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
                headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
                headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
                headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
                if settings.is_production:
                    headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
                if "cache-control" not in headers:
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)


app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    if isinstance(exc, RequestValidationError):
        return await request_validation_exception_handler(request, exc)
    if isinstance(exc, StarletteHTTPException):
        return await http_exception_handler(request, exc)
    logger.exception("Unhandled server error")
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Please try again."})


app.include_router(auth.router)
app.include_router(alumni.router)
app.include_router(admin.router)
app.include_router(admin_cards.router)
app.include_router(admin_survey.router)
app.include_router(admin_perks.router)
app.include_router(admin_users.router)
app.include_router(admin_profile_updates.router)
app.include_router(admin_profile_reminders.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/health")
def health():
    mail = email_health()
    payload = {
        "ok": True,
        "service": "CareerSense",
        "environment": settings.environment,
    }
    if settings.is_production:
        payload["email_enabled"] = bool(mail.get("email_enabled"))
        return payload
    return {
        **payload,
        "gemini_configured": bool(settings.gemini_api_key),
        "docs_enabled": settings.docs_enabled,
        "email_configured": mail["email_configured"],
        "email_enabled": mail["email_enabled"],
        "email_provider": mail["email_provider"],
        "email_scheduler": scheduler_is_enabled(),
    }
