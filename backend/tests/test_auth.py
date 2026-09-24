from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings
from app.security import TOKEN_TYPE_ACCESS, TOKEN_TYPE_REGISTRATION, create_registration_token, decode_token
from tests.conftest import auth_header, login


def test_valid_login(client):
    data = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    assert data["token_type"] == "bearer"
    assert data["user"]["role"] == "Admin"
    payload = decode_token(data["access_token"])
    assert payload["typ"] == TOKEN_TYPE_ACCESS
    assert payload["sub"] == str(data["user"]["id"])


def test_invalid_login(client):
    response = client.post("/api/auth/login", json={"email": "admin@auf.edu.ph", "password": "wrong-pass-1"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password."


def test_expired_token_rejected(client):
    token = jwt.encode(
        {
            "sub": "1",
            "typ": TOKEN_TYPE_ACCESS,
            "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        get_settings().secret_key,
        algorithm="HS256",
    )
    response = client.get("/api/auth/me", headers=auth_header(token))
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower() or "sign in" in response.json()["detail"].lower()


def test_registration_token_cannot_access_admin(client):
    token = create_registration_token(1)
    payload = decode_token(token)
    assert payload["typ"] == TOKEN_TYPE_REGISTRATION
    assert "sub" not in payload
    assert payload["did"] == "1"
    response = client.get("/api/admin/dashboard", headers=auth_header(token))
    assert response.status_code == 401


def test_registration_token_cannot_access_alumni_or_me(client):
    token = create_registration_token(1)
    assert client.get("/api/auth/me", headers=auth_header(token)).status_code == 401
    assert client.get("/api/alumni/dashboard", headers=auth_header(token)).status_code == 401
    assert client.get("/api/alumni/profile", headers=auth_header(token)).status_code == 401


def test_alumni_cannot_access_admin(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    response = client.get("/api/admin/dashboard", headers=auth_header(data["access_token"]))
    assert response.status_code == 403


def test_admin_access_token_can_read_dashboard(client):
    data = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    response = client.get("/api/admin/dashboard", headers=auth_header(data["access_token"]))
    assert response.status_code == 200
    body = response.json()
    assert "pending_approvals" in body
    assert set(body["alignment_distribution"]) == {"Aligned", "Unknown", "Misaligned"}
