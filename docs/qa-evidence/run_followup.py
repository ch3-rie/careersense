"""Follow-up ITE40 execution for cases the 9 November run left blocked or outside the set.

The PIN value, reset token, and replacement admin password are not written to the results file.
"""

from __future__ import annotations

import hmac
import json
import os
import sqlite3
import uuid
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend" / "careersense.db"
OUT = Path(__file__).with_name("execution-results-followup.json")
SECRET_FILE = Path(os.environ["TEMP"]) / "careersense-qa-secret.txt"
STAMP = uuid.uuid4().hex[:8]
REJECT_EMAIL = "qa.reject.6101f451@example.com"
LIMITED_EMAIL = "qa.admin.667341@example.com"
SUPER_EMAIL = "admin@auf.edu.ph"
SUPER_PASSWORD = "Admin@AUF2026"
REPLACEMENT = "QaAdmin@2026"


def call(method, path, *, headers=None, json_body=None, form=None, timeout=60):
    body = None
    hdrs = dict(headers or {})
    if json_body is not None:
        body = json.dumps(json_body).encode()
        hdrs["Content-Type"] = "application/json"
    elif form is not None:
        boundary = "----CareerSenseQA" + uuid.uuid4().hex
        chunks = []
        for name, value, filename in form:
            chunks.append(f"--{boundary}\r\n".encode())
            disp = f'Content-Disposition: form-data; name="{name}"'
            if filename:
                disp += f'; filename="{filename}"'
            chunks.append((disp + "\r\n").encode())
            if filename:
                chunks.append(b"Content-Type: text/plain\r\n")
            chunks.append(b"\r\n")
            chunks.append(value if isinstance(value, bytes) else str(value).encode())
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        hdrs["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = Request(API + path, data=body, headers=hdrs, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode() or "null"
            return resp.status, json.loads(raw)
    except HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw[:400]}
        return exc.code, payload


def detail(payload):
    item = payload.get("detail", payload) if isinstance(payload, dict) else payload
    if isinstance(item, list):
        return "; ".join(str(part.get("msg", part)) for part in item)
    return str(item)


def connect():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def match_pin(secret: str, stored: str) -> str | None:
    try:
        salt, digest = str(stored).split("$", 1)
    except ValueError:
        return None
    key = secret.encode("utf-8")
    for number in range(1_000_000):
        pin = f"{number:06d}"
        expected = hmac.new(key, f"{salt}:{pin}".encode("utf-8"), sha256).hexdigest()
        if hmac.compare_digest(expected, digest):
            return pin
    return None


def main():
    secret = SECRET_FILE.read_text(encoding="utf-8").strip()
    report = {"stamp": STAMP}
    health_code, health = call("GET", "/api/health")
    report["health"] = {"status": health_code, "body": health}

    code, body = call("POST", "/api/auth/login", json_body={"email": SUPER_EMAIL, "password": SUPER_PASSWORD})
    report["super_login"] = code
    token = body.get("access_token") if isinstance(body, dict) else ""
    seeded_id = (body.get("user") or {}).get("id") if isinstance(body, dict) else None
    headers = {"Authorization": f"Bearer {token}"}

    users_code, users = call("GET", "/api/admin/users", headers=headers)
    report["users_before"] = {
        "status": users_code,
        "full_active": users.get("full_active") if isinstance(users, dict) else None,
        "emails": [item.get("email") for item in (users.get("items") or [])] if isinstance(users, dict) else [],
    }
    used_numbers = set()
    if isinstance(users, dict):
        used_numbers = {str(item.get("employee_number") or "") for item in users.get("items") or []}
    employee = next(f"{number:03d}" for number in range(93, 100) if f"{number:03d}" not in used_numbers)
    super2 = f"qa.super.{STAMP}@example.com"
    create_code, created = call(
        "POST",
        "/api/admin/users",
        headers=headers,
        json_body={
            "first_name": "Second",
            "last_name": "Super",
            "email": super2,
            "employee_number": employee,
            "role": "Admin",
            "status": "Active",
            "confirm": True,
        },
    )
    created_item = created.get("item") if isinstance(created, dict) else {}
    super2_id = created_item.get("id")
    report["create_second"] = {
        "status": create_code,
        "email": super2,
        "employee_number": employee,
        "privileges_on_create": created_item.get("admin_privileges"),
        "full_admin_on_create": created_item.get("full_admin"),
        "detail": None if create_code == 200 else detail(created),
    }

    with connect() as conn:
        conn.execute("UPDATE accounts SET admin_privileges = '' WHERE id = ?", (super2_id,))
        conn.commit()
        row = conn.execute(
            "SELECT admin_privileges, status, role FROM accounts WHERE id = ?",
            (super2_id,),
        ).fetchone()
    report["privilege_cleared"] = {
        "admin_privileges": row["admin_privileges"] if row else None,
        "status": row["status"] if row else None,
        "note": "The users function always stores add_users. Empty privileges were written in the local database so this account is a second full administrator for TC-AUTH-003.",
    }

    users_code, users = call("GET", "/api/admin/users", headers=headers)
    second = next((item for item in (users.get("items") or []) if item.get("id") == super2_id), {})
    report["second_listed"] = {
        "status": users_code,
        "full_admin": second.get("full_admin"),
        "privilege_label": second.get("privilege_label"),
        "full_active": users.get("full_active") if isinstance(users, dict) else None,
    }

    deact_code, deact = call("POST", f"/api/admin/users/{super2_id}/deactivate", headers=headers)
    report["deactivate_second_while_two_full_admins"] = {
        "status": deact_code,
        "message": deact.get("message") if isinstance(deact, dict) else detail(deact),
        "resulting_status": (deact.get("item") or {}).get("status") if isinstance(deact, dict) else None,
    }
    self_code, self_body = call("POST", f"/api/admin/users/{seeded_id}/deactivate", headers=headers)
    report["deactivate_signed_in_super"] = {"status": self_code, "detail": detail(self_body)}
    still_code, still = call("POST", "/api/auth/login", json_body={"email": SUPER_EMAIL, "password": SUPER_PASSWORD})
    report["seeded_super_still_signs_in"] = {"status": still_code, "role": (still.get("user") or {}).get("role")}

    inactive_code, inactive = call(
        "POST",
        "/api/auth/login",
        json_body={"email": super2, "password": created.get("temporary_password", "")},
    )
    report["tc_auth_003"] = {
        "status": inactive_code,
        "detail": detail(inactive),
        "token_issued": bool(isinstance(inactive, dict) and inactive.get("access_token")),
    }

    # Limited admin browser precondition: replace the unknown temporary password.
    reset_code, reset_body = call("POST", "/api/admin/users/26/reset-password", headers=headers)
    temp = reset_body.get("temporary_password") if isinstance(reset_body, dict) else ""
    login_code, login_body = call(
        "POST",
        "/api/auth/login",
        json_body={"email": LIMITED_EMAIL, "password": temp},
    )
    limited_token = login_body.get("access_token") if isinstance(login_body, dict) else ""
    change_code, change_body = call(
        "POST",
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {limited_token}"},
        json_body={"current_password": temp, "new_password": REPLACEMENT},
    )
    nav_code, nav_body = call(
        "POST",
        "/api/auth/login",
        json_body={"email": LIMITED_EMAIL, "password": REPLACEMENT},
    )
    nav_token = nav_body.get("access_token") if isinstance(nav_body, dict) else ""
    nav_headers = {"Authorization": f"Bearer {nav_token}"}
    approvals_code, approvals_body = call("GET", "/api/admin/approvals", headers=nav_headers)
    users_only_code, _ = call("GET", "/api/admin/users", headers=nav_headers)
    me_code, me_body = call("GET", "/api/auth/me", headers=nav_headers)
    me_user = me_body.get("user") if isinstance(me_body, dict) else {}
    report["tc_auth_002_followup"] = {
        "reset_status": reset_code,
        "change_status": change_code,
        "change_message": change_body.get("message") if isinstance(change_body, dict) else detail(change_body),
        "login_after_change": nav_code,
        "must_change_password": me_user.get("must_change_password"),
        "full_admin": me_user.get("full_admin"),
        "admin_privileges": me_user.get("admin_privileges"),
        "users": users_only_code,
        "approvals": [approvals_code, detail(approvals_body)],
        "password_recorded": False,
    }

    # Draft expiry. One registration, then the draft clock is moved in the local database.
    expire_email = f"qa.expire.{STAMP}@example.com"
    resume = b"QA Expiry Candidate\nUnmatched Person\nOffice Assistant\n"
    reg_code, reg = call(
        "POST",
        "/api/auth/register",
        form=[
            ("email", expire_email, None),
            ("password", "Alumni@2026", None),
            ("confirm_password", "Alumni@2026", None),
            ("privacy_consent", "true", None),
            ("resume", resume, "qa-expire.txt"),
        ],
        timeout=120,
    )
    reg_token = reg.get("registration_token") if isinstance(reg, dict) else ""
    with connect() as conn:
        before = conn.execute(
            "SELECT id, expires_at FROM registration_drafts WHERE personal_email = ?",
            (expire_email,),
        ).fetchone()
        conn.execute(
            "UPDATE registration_drafts SET expires_at = '2000-01-01 00:00:00' WHERE personal_email = ?",
            (expire_email,),
        )
        conn.commit()
    complete_code, complete = call(
        "POST",
        "/api/auth/register/complete",
        json_body={"registration_token": reg_token, "first_name": "QA", "last_name": "Expiry"},
    )
    login_expired_code, login_expired = call(
        "POST",
        "/api/auth/login",
        json_body={"email": expire_email, "password": "Alumni@2026"},
    )
    with connect() as conn:
        left = conn.execute(
            "SELECT id FROM registration_drafts WHERE personal_email = ?",
            (expire_email,),
        ).fetchone()
        account = conn.execute(
            "SELECT id FROM accounts WHERE personal_email = ?",
            (expire_email,),
        ).fetchone()
    report["tc_reg_010"] = {
        "email": expire_email,
        "register_status": reg_code,
        "account_created": reg.get("account_created") if isinstance(reg, dict) else None,
        "draft_id": before["id"] if before else None,
        "expires_at_before_move": str(before["expires_at"]) if before else None,
        "complete_status": complete_code,
        "complete_detail": detail(complete),
        "login_status": login_expired_code,
        "login_detail": detail(login_expired),
        "draft_remaining": bool(left),
        "account_remaining": bool(account),
        "clock": "expires_at was set to 2000-01-01 in the local database. The test did not wait 24 hours.",
    }

    # PIN expiry and a completed reset on the rejected QA account. The password hash is restored.
    with connect() as conn:
        original = conn.execute(
            "SELECT id, password_hash, token_version, must_change_password, password_changed_at FROM accounts WHERE personal_email = ?",
            (REJECT_EMAIL,),
        ).fetchone()
    report["pin_account"] = {"email": REJECT_EMAIL, "found": bool(original)}
    if not original:
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(OUT)
        return

    try:
        ask_code, ask = call("POST", "/api/auth/forgot-password", json_body={"email": REJECT_EMAIL})
        with connect() as conn:
            challenge = conn.execute(
                "SELECT id, pin_hash, expires_at, account_id FROM password_reset_verifications WHERE account_id = ? ORDER BY id DESC LIMIT 1",
                (original["id"],),
            ).fetchone()
            conn.execute(
                "UPDATE password_reset_verifications SET expires_at = '2000-01-01 00:00:00' WHERE id = ?",
                (challenge["id"],),
            )
            conn.commit()
            audit = conn.execute(
                "SELECT action_type FROM admin_logs WHERE target_id = ? ORDER BY id DESC LIMIT 4",
                (str(original["id"]),),
            ).fetchall()
        expired_code, expired = call(
            "POST",
            "/api/auth/forgot-password/verify",
            json_body={"email": REJECT_EMAIL, "pin": "000000"},
        )
        report["tc_pwd_002"] = {
            "request_status": ask_code,
            "request_message": ask.get("message") if isinstance(ask, dict) else detail(ask),
            "challenge_id": challenge["id"] if challenge else None,
            "expires_at_before_move": str(challenge["expires_at"]) if challenge else None,
            "verify_status": expired_code,
            "verify_detail": detail(expired),
            "recent_audit": [row["action_type"] for row in audit],
            "clock": "The challenge expires_at was set to 2000-01-01. The test did not wait 10 minutes.",
            "inbox": "No inbox was checked. email_enabled was false.",
        }

        ask2_code, ask2 = call("POST", "/api/auth/forgot-password", json_body={"email": REJECT_EMAIL})
        with connect() as conn:
            fresh = conn.execute(
                "SELECT id, pin_hash FROM password_reset_verifications WHERE account_id = ? ORDER BY id DESC LIMIT 1",
                (original["id"],),
            ).fetchone()
        issued = match_pin(secret, fresh["pin_hash"]) if fresh else None
        verify_code, verified = call(
            "POST",
            "/api/auth/forgot-password/verify",
            json_body={"email": REJECT_EMAIL, "pin": issued or "000000"},
        )
        reset_token = verified.get("reset_token") if isinstance(verified, dict) else ""
        new_password = "QaReset@" + STAMP
        reset_code, reset_done = call(
            "POST",
            "/api/auth/reset-password",
            json_body={"reset_token": reset_token, "new_password": new_password},
        )
        new_login_code, new_login = call(
            "POST",
            "/api/auth/login",
            json_body={"email": REJECT_EMAIL, "password": new_password},
        )
        report["tc_pwd_003"] = {
            "request_status": ask2_code,
            "request_message": ask2.get("message") if isinstance(ask2, dict) else detail(ask2),
            "pin_recovered": bool(issued),
            "pin_recorded": False,
            "verify_status": verify_code,
            "verify_message": verified.get("message") if isinstance(verified, dict) else detail(verified),
            "reset_token_recorded": False,
            "reset_status": reset_code,
            "reset_message": reset_done.get("message") if isinstance(reset_done, dict) else detail(reset_done),
            "login_with_new_password": new_login_code,
            "login_status_value": (new_login.get("user") or {}).get("status") if isinstance(new_login, dict) else None,
        }
    finally:
        with connect() as conn:
            conn.execute(
                """
                UPDATE accounts
                SET password_hash = ?, token_version = ?, must_change_password = ?, password_changed_at = ?
                WHERE id = ?
                """,
                (
                    original["password_hash"],
                    original["token_version"],
                    original["must_change_password"],
                    original["password_changed_at"],
                    original["id"],
                ),
            )
            conn.commit()
        restored_code, restored = call(
            "POST",
            "/api/auth/login",
            json_body={"email": REJECT_EMAIL, "password": "Alumni@2026"},
        )
        report["password_restored"] = {
            "login_status": restored_code,
            "account_status": (restored.get("user") or {}).get("status") if isinstance(restored, dict) else detail(restored),
        }

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
