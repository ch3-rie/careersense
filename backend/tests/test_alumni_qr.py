from app.services.alumni_qr import alumni_qr_token
from tests.conftest import auth_header, login


def test_each_active_alumnus_has_one_stable_qr(client):
    maria = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    liza = login(client, "liza.torres@gmail.com", "Alumni@2026")
    maria_headers = auth_header(maria["access_token"])
    liza_headers = auth_header(liza["access_token"])

    first = client.get("/api/alumni/qr", headers=maria_headers)
    again = client.get("/api/alumni/qr", headers=maria_headers)
    other = client.get("/api/alumni/qr", headers=liza_headers)
    assert first.status_code == 200, first.text
    assert first.json() == again.json()
    assert first.json()["student_number"] == "2020-0001"
    assert first.json()["name"] == "Maria Cruz Reyes"
    assert first.json()["course"] == "Bachelor of Science in Information Technology"
    assert first.json()["college"] == "College of Computer Studies"
    assert first.json()["year_graduated"] == "2022"
    assert "guardian" not in first.json()
    assert "email" not in first.json()
    assert other.json()["student_number"] == "2018-0330"
    assert other.json()["name"] == "Liza Pineda Torres"
    assert other.json()["student_number"] != first.json()["student_number"]

    maria_image = client.get("/api/alumni/qr/image", headers=maria_headers)
    liza_image = client.get("/api/alumni/qr/image", headers=liza_headers)
    assert maria_image.status_code == 200
    assert maria_image.headers["content-type"].startswith("image/svg+xml")
    assert maria_image.content == client.get("/api/alumni/qr/image", headers=maria_headers).content
    assert maria_image.content != liza_image.content
    assert b"2020-0001" not in maria_image.content
    assert b"maria.reyes" not in maria_image.content
    assert b"Both Parents" not in maria_image.content


def test_qr_verification_shows_only_academic_details(client):
    maria = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    token = alumni_qr_token(maria["user"]["id"])
    verified = client.get(f"/api/public/alumni-qr/{token}")
    assert verified.status_code == 200, verified.text
    body = verified.json()
    assert body["student_number"] == "2020-0001"
    assert body["name"] == "Maria Cruz Reyes"
    assert set(body) == {"student_number", "name", "course", "college", "year_graduated"}
    forged = client.get(f"/api/public/alumni-qr/{token[:-1]}{'a' if token[-1] != 'a' else 'b'}")
    assert forged.status_code == 404
    assert client.get("/api/public/alumni-qr/v1.1.not-a-real-code").status_code == 404


def test_pending_alumni_cannot_open_alumni_qr(client):
    pending = login(client, "juan.delacruz@gmail.com", "Alumni@2026")
    headers = auth_header(pending["access_token"])
    assert client.get("/api/alumni/qr", headers=headers).status_code == 403
    assert client.get("/api/alumni/qr/image", headers=headers).status_code == 403
