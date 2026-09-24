from app.rate_limit import client_ip, login_limiter, set_rate_limit_enabled


def test_login_rate_limit(client):
    set_rate_limit_enabled(True)
    login_limiter.reset()
    original = login_limiter.limit
    login_limiter.limit = 3
    try:
        blocked = False
        for _ in range(6):
            response = client.post(
                "/api/auth/login",
                json={"email": "admin@auf.edu.ph", "password": "wrong-pass-1"},
            )
            if response.status_code == 429:
                blocked = True
                assert "too many" in response.json()["detail"].lower()
                break
        assert blocked
    finally:
        login_limiter.limit = original
        login_limiter.reset()
        set_rate_limit_enabled(False)


def test_client_ip_ignores_spoofed_forwarded_for_by_default():
    from types import SimpleNamespace

    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.9"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert client_ip(request) == "127.0.0.1"


def test_login_rate_limit(client):
    set_rate_limit_enabled(True)
    login_limiter.reset()
    original = login_limiter.limit
    login_limiter.limit = 3
    try:
        blocked = False
        for _ in range(6):
            response = client.post(
                "/api/auth/login",
                json={"email": "admin@auf.edu.ph", "password": "wrong-pass-1"},
            )
            if response.status_code == 429:
                blocked = True
                assert "too many" in response.json()["detail"].lower()
                break
        assert blocked
    finally:
        login_limiter.limit = original
        login_limiter.reset()
        set_rate_limit_enabled(False)
