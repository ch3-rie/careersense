from collections.abc import Generator
import logging

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger("careersense")
settings = get_settings()

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine_kwargs: dict = {
    "connect_args": connect_args,
    "pool_pre_ping": True,
}
if not settings.database_url.startswith("sqlite"):
    engine_kwargs.update(pool_size=10, max_overflow=20, pool_recycle=1800)

engine = create_engine(settings.database_url, **engine_kwargs)

if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _column_names(inspector, table: str) -> set[str]:
    if table not in inspector.get_table_names():
        return set()
    return {col["name"] for col in inspector.get_columns(table)}


def _has_unique_on(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    for ix in inspector.get_indexes(table):
        if ix.get("unique") and list(ix.get("column_names") or []) == [column]:
            return True
    try:
        for uc in inspector.get_unique_constraints(table):
            if list(uc.get("column_names") or []) == [column]:
                return True
    except NotImplementedError:
        pass
    return False


def _ensure_columns(bind, table: str, columns: list[tuple[str, str]]) -> None:
    inspector = inspect(bind)
    existing = _column_names(inspector, table)
    if not existing:
        return
    for name, coltype in columns:
        if name in existing:
            continue
        with bind.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {coltype}"))
        logger.info("Added %s.%s", table, name)
        existing.add(name)


def ensure_runtime_schema(bind=None) -> None:
    """Apply additive schema fixes for databases created before Alembic."""
    bind = bind or engine
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=bind)
    inspector = inspect(bind)
    if "accounts" not in inspector.get_table_names():
        return

    cols = _column_names(inspector, "accounts")
    if "password_changed_at" not in cols:
        dialect = bind.dialect.name
        coltype = "TIMESTAMPTZ" if dialect == "postgresql" else "DATETIME"
        with bind.begin() as conn:
            conn.execute(text(f"ALTER TABLE accounts ADD COLUMN password_changed_at {coltype}"))
        logger.info("Added accounts.password_changed_at")

    inspector = inspect(bind)
    if not _has_unique_on(inspector, "accounts", "linked_student_id"):
        try:
            with bind.begin() as conn:
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX uq_accounts_linked_student_id "
                        "ON accounts (linked_student_id)"
                    )
                )
        except Exception as exc:
            logger.warning(
                "Could not add unique index on accounts.linked_student_id (%s). "
                "Resolve duplicate student links before retrying.",
                exc,
            )

    inspector = inspect(bind)
    profile_cols = _column_names(inspector, "alumni_profiles")
    if profile_cols and "job_timeline_ready" not in profile_cols:
        dialect = bind.dialect.name
        default = "FALSE" if dialect == "postgresql" else "0"
        with bind.begin() as conn:
            conn.execute(
                text(f"ALTER TABLE alumni_profiles ADD COLUMN job_timeline_ready BOOLEAN DEFAULT {default}")
            )
        logger.info("Added alumni_profiles.job_timeline_ready")

    _ensure_columns(
        bind,
        "alumni_profiles",
        [
            ("phone", "VARCHAR(40)"),
            ("city", "VARCHAR(120)"),
            ("photo_path", "VARCHAR(500)"),
            ("photo_mime", "VARCHAR(120)"),
            ("cover_path", "VARCHAR(500)"),
            ("cover_mime", "VARCHAR(120)"),
            ("bio", "TEXT"),
            ("address", "VARCHAR(240)"),
            ("birth_date", "DATE"),
        ],
    )
    _ensure_columns(
        bind,
        "alumni_jobs",
        [
            ("industry", "VARCHAR(120)"),
            ("location", "VARCHAR(120)"),
            ("description", "TEXT"),
        ],
    )
    dialect = bind.dialect.name
    json_type = "JSONB" if dialect == "postgresql" else "TEXT"
    dt_type = "TIMESTAMPTZ" if dialect == "postgresql" else "DATETIME"
    _ensure_columns(
        bind,
        "alumni_cards",
        [
            ("submitted_at", dt_type),
            ("pickup_ready_at", dt_type),
            ("pickup_location", "VARCHAR(200)"),
            ("application_json", json_type),
        ],
    )
    _ensure_columns(
        bind,
        "alumni_perks",
        [
            ("partner", "VARCHAR(160)"),
            ("category", "VARCHAR(80)"),
            ("eligibility", "TEXT"),
            ("contact", "VARCHAR(255)"),
            ("website", "VARCHAR(500)"),
            ("image_path", "VARCHAR(500)"),
            ("image_mime", "VARCHAR(120)"),
        ],
    )
    _ensure_columns(
        bind,
        "accounts",
        [
            ("first_name", "VARCHAR(80)"),
            ("last_name", "VARCHAR(80)"),
            ("must_change_password", "BOOLEAN"),
            ("last_login_at", dt_type),
            ("token_version", "INTEGER"),
        ],
    )
    _ensure_columns(
        bind,
        "tracer_submissions",
        [
            ("survey_version", "INTEGER"),
        ],
    )
    _ensure_columns(
        bind,
        "alumni_notifications",
        [
            ("link", "VARCHAR(200)"),
        ],
    )
    _ensure_columns(
        bind,
        "alumni_badges",
        [
            ("award_metadata", json_type),
        ],
    )
