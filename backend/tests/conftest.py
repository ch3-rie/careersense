import os
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
TEST_DB = TEST_DIR / f"_test_{os.getpid()}.db"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production-use-123456"
os.environ["ENVIRONMENT"] = "development"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["ENABLE_DOCS"] = "true"
os.environ["EMAIL_ENABLED"] = "false"
os.environ["EMAIL_API_KEY"] = ""
os.environ["EMAIL_PROVIDER"] = ""
os.environ["SMTP_HOST"] = ""
os.environ["EMAIL_SCHEDULER_ENABLED"] = "false"

for leftover in (TEST_DIR / "_test.db", TEST_DB):
    try:
        leftover.unlink()
    except OSError:
        pass

from fastapi.testclient import TestClient
import pytest

from app.db import Base, SessionLocal, engine
from app.main import app


@pytest.fixture(scope="session")
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if TEST_DB.exists():
        try:
            TEST_DB.unlink()
        except OSError:
            pass


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, email: str, password: str):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


SAMPLE_RESUME = b"Maria Cruz Reyes\nBachelor of Science in Information Technology 2022\nSoftware Engineer\nSkills: Python, SQL\n"


def unique_resume(first_name: str = "Unique", last_name: str = "Graduate") -> bytes:
    """Resume text that does not match seeded university records by name."""
    return (
        f"{first_name} {last_name}\n"
        "Bachelor of Science in Information Technology 2024\n"
        "Software Engineer\n"
        "Skills: Python, SQL\n"
    ).encode()
