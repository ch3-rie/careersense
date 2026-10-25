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

    _ensure_columns(
        bind,
        "accounts",
        [
            ("employee_number", "VARCHAR(3)"),
            ("admin_privileges", "VARCHAR(80)"),
        ],
    )
    try:
        with bind.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_accounts_employee_number "
                    "ON accounts (employee_number)"
                )
            )
    except Exception as exc:
        logger.warning("Could not add unique index on accounts.employee_number (%s).", exc)
    if "alumni_perks" in inspector.get_table_names():
        perk_flag = "BOOLEAN NOT NULL DEFAULT FALSE" if bind.dialect.name == "postgresql" else "INTEGER NOT NULL DEFAULT 0"
        _ensure_columns(bind, "alumni_perks", [("valid_until_further_notice", perk_flag)])

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
            ("no_employment_reason", "TEXT"),
            ("unemployment_reason", "VARCHAR(40)"),
            ("unemployment_details", "TEXT"),
            ("employment_answer_before", "VARCHAR(8)"),
            ("resume_document", "JSONB" if bind.dialect.name == "postgresql" else "JSON"),
            ("resume_activity_seeded", "BOOLEAN"),
        ],
    )
    inspector = inspect(bind)
    profile_cols = _column_names(inspector, "alumni_profiles")
    if profile_cols and "currently_unemployed" not in profile_cols:
        dialect = bind.dialect.name
        default = "FALSE" if dialect == "postgresql" else "0"
        with bind.begin() as conn:
            conn.execute(
                text(
                    f"ALTER TABLE alumni_profiles ADD COLUMN currently_unemployed BOOLEAN DEFAULT {default}"
                )
            )
        logger.info("Added alumni_profiles.currently_unemployed")
    _ensure_columns(
        bind,
        "further_studies",
        [
            ("institution_address", "VARCHAR(240)"),
        ],
    )
    _ensure_columns(
        bind,
        "alumni_certifications",
        [
            ("awarded_on", "VARCHAR(20)"),
            ("verification_url", "VARCHAR(500)"),
            ("certificate_path", "VARCHAR(500)"),
            ("certificate_mime", "VARCHAR(120)"),
            ("certificate_filename", "VARCHAR(255)"),
        ],
    )
    _ensure_columns(
        bind,
        "alumni_jobs",
        [
            ("industry", "VARCHAR(120)"),
            ("location", "VARCHAR(120)"),
            ("salary_range", "VARCHAR(80)"),
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
    _ensure_columns(
        bind,
        "academic_programs",
        [
            ("parent_id", "INTEGER"),
            ("kind", "VARCHAR(32) DEFAULT ''"),
            ("review_status", "VARCHAR(20) DEFAULT 'on_record'"),
        ],
    )
    _relax_university_email(bind)


def _relax_university_email(bind) -> None:
    """Allow registrar imports that have a student number but no email address."""
    inspector = inspect(bind)
    if "university_records" not in inspector.get_table_names():
        return
    email = next((col for col in inspector.get_columns("university_records") if col["name"] == "personal_email"), None)
    if email is None or email.get("nullable", True):
        return
    if bind.dialect.name == "postgresql":
        statement = "ALTER TABLE university_records ALTER COLUMN personal_email DROP NOT NULL"
        if hasattr(bind, "exec_driver_sql") and not hasattr(bind, "raw_connection"):
            bind.exec_driver_sql(statement)
        else:
            with bind.begin() as conn:
                conn.execute(text(statement))
        logger.info("Made university_records.personal_email optional")
        return
    if bind.dialect.name != "sqlite" or not hasattr(bind, "raw_connection"):
        logger.warning("Could not relax university_records.personal_email on %s", bind.dialect.name)
        return
    dbapi_conn = bind.raw_connection()
    cursor = dbapi_conn.cursor()
    try:
        try:
            dbapi_conn.rollback()
        except Exception:
            pass
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute("BEGIN")
        cursor.execute(
            """
            CREATE TABLE university_records__email_optional (
                student_id VARCHAR(40) NOT NULL PRIMARY KEY,
                first_name VARCHAR(80) NOT NULL,
                middle_name VARCHAR(80) NOT NULL DEFAULT '',
                last_name VARCHAR(80) NOT NULL,
                personal_email VARCHAR(255),
                degree VARCHAR(200) NOT NULL,
                year_graduated VARCHAR(8) NOT NULL DEFAULT '',
                course_code VARCHAR(40) NOT NULL DEFAULT '',
                college VARCHAR(160) NOT NULL DEFAULT ''
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO university_records__email_optional (
                student_id, first_name, middle_name, last_name, personal_email,
                degree, year_graduated, course_code, college
            )
            SELECT student_id, first_name, COALESCE(middle_name, ''), last_name,
                NULLIF(TRIM(personal_email), ''),
                degree, COALESCE(year_graduated, ''), COALESCE(course_code, ''), COALESCE(college, '')
            FROM university_records
            """
        )
        cursor.execute("DROP TABLE university_records")
        cursor.execute("ALTER TABLE university_records__email_optional RENAME TO university_records")
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_university_records_personal_email "
            "ON university_records (personal_email)"
        )
        cursor.execute("COMMIT")
        logger.info("Made university_records.personal_email optional")
    except Exception:
        try:
            cursor.execute("ROLLBACK")
        except Exception:
            pass
        logger.exception("Could not relax university_records.personal_email")
        raise
    finally:
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass
        dbapi_conn.close()
