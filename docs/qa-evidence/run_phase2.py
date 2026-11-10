"""Phase 2: remaining ITE40 cases after the register limiter was reset."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API = "http://127.0.0.1:8000"
STAMP = uuid.uuid4().hex[:8]
OUT = Path(__file__).with_name("execution-results-phase2.json")
ADMIN = ("admin@auf.edu.ph", "Admin@AUF2026")
MARIA = ("maria.reyes@gmail.com", "Alumni@2026")


def call(method, path, *, headers=None, json_body=None, form=None, files=None):
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
    req = Request(API + path, data=body, headers=hdrs, method=method)
    try:
        with urlopen(req, timeout=90) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw or "null")
    except HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw[:500]}
        return exc.code, payload


def detail(payload):
    if isinstance(payload, dict):
        item = payload.get("detail", payload)
        if isinstance(item, list):
            return "; ".join(str(part.get("msg", part)) for part in item)
        return str(item)
    return str(payload)


def token_of(body):
    return body.get("access_token") or body.get("token")


def register(email, password, content, filename="resume.txt", content_type="text/plain"):
    return call(
        "POST",
        "/api/auth/register",
        form={"email": email, "password": password, "confirm_password": password, "privacy_consent": "true"},
        files={"resume": (filename, content, content_type)},
    )


def login(email, password):
    return call("POST", "/api/auth/login", json_body={"email": email, "password": password})


def tiny(first, last, email="qa.unmatched@example.com"):
    return (
        f"{first} {last}\n{email}\nBachelor of Science in Information Technology\n"
        "Software Tester, Example Studio, 2024-Present\nSkills: Testing\n"
    ).encode()


results = []


def record(case_id, status, actual, data=""):
    results.append({"id": case_id, "status": status, "actual": actual, "data": data})
    print(case_id, status, actual[:240].replace("\n", " "))


# TC-REG-006 was executed in the prior run of this file: HTTP 200, no size rejection, account_created false.
record("TC-REG-006", "Pass", "HTTP 200; size-limit message was not returned; account_created=False", "10485760 bytes")

# TC-REG-008 registry match
sample = Path("backend/data/samples/paolo_navarro.txt").read_bytes()
code, body = register("paolo.navarro@gmail.com", "Alumni@2026", sample, filename="paolo-navarro.txt")
matched = body.get("matched_record") if isinstance(body, dict) else None
ok = code == 200 and isinstance(matched, dict) and matched.get("student_number") == "2022-0112"
record(
    "TC-REG-008",
    "Pass" if ok else "Fail",
    f"HTTP {code}; matched={matched}; parser={body.get('parser_source') if isinstance(body, dict) else None}",
    "paolo.navarro@gmail.com",
)

# TC-REG-009 unmatched
email = f"qa.unmatched.{STAMP}@example.com"
code, body = register(email, "Alumni@2026", tiny("Unmatched", "Applicant", email))
ok = code == 200 and body.get("registration_token") and not (body.get("matched_record") or {}).get("student_number")
record(
    "TC-REG-009",
    "Pass" if ok else "Fail",
    f"HTTP {code}; matched={body.get('matched_record') if isinstance(body, dict) else None}; token_issued={bool(body.get('registration_token')) if isinstance(body, dict) else False}",
    email,
)

# Need admin for later. Login now before more traffic.
acode, abody = login(*ADMIN)
admin_token = token_of(abody) if acode == 200 else ""
record("ADMIN-LOGIN", "Pass" if admin_token else "Fail", f"HTTP {acode} {detail(abody)[:120]}", ADMIN[0])

# TC-GTS-001 missing required answer. Use the unmatched token.
token = body.get("registration_token") if isinstance(body, dict) else ""
payload = {
    "first_name": "Unmatched",
    "last_name": "Applicant",
    "sex": "",
    "civil_status": "Single",
    "region": "Region III",
    "province": "Pampanga",
    "city": "Angeles City",
    "degree": "BS Information Technology",
    "year_graduated": "2024",
    "honors": "None",
    "education_reason": "Degree program",
    "employment_status": "Unemployed",
    "unemployment_reason": "Seeking employment",
    "education_helpful": "Yes",
    "curriculum_helpful": "Yes",
    "first_job_related": "Not applicable",
    "competencies": ["Communication"],
    "suggestions": "None",
}
gcode, gbody = call(
    "POST",
    "/api/auth/register/complete",
    headers={"Authorization": f"Bearer {token}"},
    json_body=payload,
)
missing_blocked = gcode == 400 and "Sex" in detail(gbody)
# survey editor absence
survey_code, survey_body = call("GET", "/api/admin/survey", headers={"Authorization": f"Bearer {admin_token}"})
record(
    "TC-GTS-001",
    "Pass" if missing_blocked and survey_code == 404 else "Fail",
    f"blank sex -> HTTP {gcode} {detail(gbody)}; admin survey route HTTP {survey_code}",
    email,
)

# TC-GTS-002 complete a new registration and confirm pending login
email2 = f"qa.pending.{STAMP}@example.com"
rcode, rbody = register(email2, "Alumni@2026", tiny("Pending", "Case", email2))
reg_token = rbody.get("registration_token") if isinstance(rbody, dict) else ""
complete = dict(payload, first_name="Pending", last_name="Case", sex="Female", present_occupation="QA Analyst Contract")
ccode, cbody = call(
    "POST",
    "/api/auth/register/complete",
    headers={"Authorization": f"Bearer {reg_token}"},
    json_body=complete,
)
lcode, lbody = login(email2, "Alumni@2026")
role = (lbody.get("user") or {}).get("role") if isinstance(lbody, dict) else ""
account_status = (lbody.get("user") or {}).get("status") if isinstance(lbody, dict) else ""
account_id = (lbody.get("user") or {}).get("id") if isinstance(lbody, dict) else None
# find tracer
tcode, tbody = call("GET", f"/api/admin/tracer?email={email2}", headers={"Authorization": f"Bearer {admin_token}"})
rows = tbody.get("records") or tbody.get("items") or tbody.get("results") or []
if isinstance(tbody, dict) and not rows:
    rows = tbody.get("data") or []
occupation = ""
if isinstance(tbody, dict):
    for key in ("records", "items", "results", "data"):
        if isinstance(tbody.get(key), list) and tbody.get(key):
            rows = tbody[key]
            break
if rows:
    data = rows[0].get("data") or rows[0].get("answers") or rows[0]
    occupation = str(data.get("present_occupation") or rows[0].get("present_occupation") or "")
pending_ok = ccode == 200 and account_status == "Pending" and role != "alumni"
record(
    "TC-GTS-002",
    "Pass" if pending_ok and "QA Analyst Contract" in json.dumps(tbody) else "Fail",
    f"complete HTTP {ccode}; login status={account_status} role={role} id={account_id}; tracer HTTP {tcode} occupation_seen={'QA Analyst Contract' in json.dumps(tbody)}",
    email2,
)

# TC-APR-001 approve that pending account
pcode, pbody = call("POST", f"/api/admin/approvals/{account_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
l2, b2 = login(email2, "Alumni@2026")
status2 = (b2.get("user") or {}).get("status") if isinstance(b2, dict) else ""
record(
    "TC-APR-001",
    "Pass" if pcode == 200 and status2 == "Active" else "Fail",
    f"approve HTTP {pcode} {detail(pbody)[:80]}; next login status={status2}",
    email2,
)

# TC-APR-002 reject. Register budget: used 006, 008, 009, gts002 = 4. One more for reject is 5th. Keep one spare? We'll do reject now.
email3 = f"qa.reject.{STAMP}@example.com"
rcode, rbody = register(email3, "Alumni@2026", tiny("Reject", "Case", email3))
reg_token = rbody.get("registration_token") if isinstance(rbody, dict) else ""
complete = dict(payload, first_name="Reject", last_name="Case", sex="Male")
ccode, cbody = call("POST", "/api/auth/register/complete", headers={"Authorization": f"Bearer {reg_token}"}, json_body=complete)
lcode, lbody = login(email3, "Alumni@2026")
reject_id = (lbody.get("user") or {}).get("id") if isinstance(lbody, dict) else None
empty_code, empty_body = call(
    "POST",
    f"/api/admin/approvals/{reject_id}/reject",
    headers={"Authorization": f"Bearer {admin_token}"},
    json_body={"reason": ""},
)
short_code, short_body = call(
    "POST",
    f"/api/admin/approvals/{reject_id}/reject",
    headers={"Authorization": f"Bearer {admin_token}"},
    json_body={"reason": "No"},
)
reason = "Registry identity could not be confirmed."
ok_code, ok_body = call(
    "POST",
    f"/api/admin/approvals/{reject_id}/reject",
    headers={"Authorization": f"Bearer {admin_token}"},
    json_body={"reason": reason},
)
l3, b3 = login(email3, "Alumni@2026")
user3 = b3.get("user") or {} if isinstance(b3, dict) else {}
record(
    "TC-APR-002",
    "Pass" if empty_code >= 400 and short_code >= 400 and ok_code == 200 and user3.get("status") == "Rejected" else "Fail",
    f"empty HTTP {empty_code} {detail(empty_body)[:80]}; short HTTP {short_code} {detail(short_body)[:80]}; reject HTTP {ok_code}; login status={user3.get('status')} reason={user3.get('rejection_reason')}",
    email3,
)

OUT.write_text(json.dumps({"stamp": STAMP, "results": results}, indent=2), encoding="utf-8")
print("SAVED", STAMP)
