"""Execute the ITE40 CareerSense cases against the local API. Prints a JSON report."""

from __future__ import annotations

import json
import mimetypes
import uuid
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API = "http://127.0.0.1:8000"
OUT = Path(__file__).with_name("execution-results.json")
STAMP = uuid.uuid4().hex[:8]


def call(method: str, path: str, *, data=None, headers=None, json_body=None, files=None, form=None):
    url = API + path
    body = None
    hdrs = dict(headers or {})
    if json_body is not None:
        body = json.dumps(json_body).encode()
        hdrs["Content-Type"] = "application/json"
    elif form is not None or files is not None:
        boundary = "----CareerSenseQA" + uuid.uuid4().hex
        chunks = []

        def add(name, value, filename=None, content_type=None):
            chunks.append(f"--{boundary}\r\n".encode())
            disp = f'Content-Disposition: form-data; name="{name}"'
            if filename:
                disp += f'; filename="{filename}"'
            chunks.append((disp + "\r\n").encode())
            if content_type:
                chunks.append(f"Content-Type: {content_type}\r\n".encode())
            chunks.append(b"\r\n")
            chunks.append(value if isinstance(value, bytes) else str(value).encode())
            chunks.append(b"\r\n")

        for key, value in (form or {}).items():
            add(key, value)
        for key, (filename, content, content_type) in (files or {}).items():
            add(key, content, filename, content_type)
        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        hdrs["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif data is not None:
        body = data
    req = Request(url, data=body, headers=hdrs, method=method)
    try:
        with urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw.decode() or "null")
    except HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return exc.code, payload


def detail(payload):
    if isinstance(payload, dict):
        item = payload.get("detail", payload)
        if isinstance(item, list):
            return "; ".join(str(part.get("msg", part)) for part in item)
        return str(item)
    return str(payload)


def register(email, password, content: bytes, filename="resume.txt", content_type="text/plain"):
    return call(
        "POST",
        "/api/auth/register",
        form={
            "email": email,
            "password": password,
            "confirm_password": password,
            "privacy_consent": "true",
        },
        files={"resume": (filename, content, content_type)},
    )


def login(email, password):
    return call("POST", "/api/auth/login", json_body={"email": email, "password": password})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def tiny_resume(first="QA", last="Tester"):
    return (
        f"{first} {last}\n"
        "qa.tester@example.com\n"
        "Bachelor of Science in Information Technology\n"
        "Software Tester, Example Studio, 2024-Present\n"
        "Skills: Testing\n"
    ).encode()


results = []


def record(case_id, data_used, status_code, payload, status, actual, evidence):
    results.append(
        {
            "id": case_id,
            "data": data_used,
            "http": status_code,
            "status": status,
            "actual": actual,
            "evidence": evidence,
        }
    )
    print(case_id, status, actual[:180].replace("\n", " "))


# TC-REG-002
email = f"qa.reg002.{STAMP}@example.com"
code, body = register(email, "Abcdef1", tiny_resume())
ok = code == 400 and "at least 8 characters" in detail(body)
record("TC-REG-002", "password length 7", code, body, "Pass" if ok else "Fail", detail(body), "EV-REG-002")

# TC-REG-003
email = f"qa.reg003.{STAMP}@example.com"
code, body = register(email, "abcdefgh", tiny_resume())
ok = code == 400 and "at least 8 characters" in detail(body)
record("TC-REG-003", "abcdefgh", code, body, "Pass" if ok else "Fail", detail(body), "EV-REG-003")

# TC-REG-004
email = f"qa.reg004.{STAMP}@example.com"
code, body = register(email, "Alumni@2026", b"", filename="empty.txt")
ok = code == 400 and "empty" in detail(body).lower()
record("TC-REG-004", "empty.txt", code, body, "Pass" if ok else "Fail", detail(body), "EV-REG-004")

# TC-REG-005
email = f"qa.reg005.{STAMP}@example.com"
jpeg = b"\xff\xd8\xff\xd9"
code, body = register(email, "Alumni@2026", jpeg, filename="photo.jpg", content_type="image/jpeg")
ok = code == 400 and "PDF, DOCX, or TXT" in detail(body)
record("TC-REG-005", "photo.jpg", code, body, "Pass" if ok else "Fail", detail(body), "EV-REG-005")

# TC-REG-007 before the valid starts, while budget remains. 10MB+1 may be slow but local.
email = f"qa.reg007.{STAMP}@example.com"
over = b"A" * (10 * 1024 * 1024 + 1)
code, body = register(email, "Alumni@2026", over, filename="over.txt")
ok = code == 400 and "10 MB or smaller" in detail(body)
record("TC-REG-007", "10485761 bytes", code, body, "Pass" if ok else "Fail", detail(body), "EV-REG-007")

# TC-REG-001 valid draft, then login must not open an account
email = f"qa.reg001.{STAMP}@example.com"
code, body = register(email, "Alumni@2026", tiny_resume("Draft", "Only"))
login_code, login_body = login(email, "Alumni@2026")
ok = (
    code == 200
    and body.get("account_created") is False
    and body.get("registration_token")
    and login_code == 401
)
record(
    "TC-REG-001",
    email,
    code,
    body,
    "Pass" if ok else "Fail",
    f"register {code} account_created={body.get('account_created') if isinstance(body, dict) else None}; login {login_code} {detail(login_body)}",
    "EV-REG-001",
)

OUT.write_text(json.dumps({"stamp": STAMP, "phase": 1, "results": results}, indent=2), encoding="utf-8")
print("PHASE1", STAMP, "count", len(results))
