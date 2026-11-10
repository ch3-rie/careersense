"""Phase 3: retest the cases whose first attempt used the wrong request shape."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API = "http://127.0.0.1:8000"
STAMP = uuid.uuid4().hex[:8]
OUT = Path(__file__).with_name("execution-results-phase3.json")
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
            raw = resp.read().decode(errors="replace")
            try:
                return resp.status, json.loads(raw or "null")
            except json.JSONDecodeError:
                return resp.status, {"raw_type": resp.headers.get("Content-Type", ""), "length": len(raw)}
    except HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw[:400]}
        return exc.code, payload


def detail(payload):
    if isinstance(payload, dict):
        item = payload.get("detail", payload.get("message", payload))
        if isinstance(item, list):
            return "; ".join(str(part.get("msg", part)) for part in item)
        return str(item)
    return str(payload)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def login(email, password):
    return call("POST", "/api/auth/login", json_body={"email": email, "password": password})


def register(email, content):
    return call(
        "POST",
        "/api/auth/register",
        form={"email": email, "password": "Alumni@2026", "confirm_password": "Alumni@2026", "privacy_consent": "true"},
        files={"resume": ("resume.txt", content, "text/plain")},
    )


def resume(first, last, email):
    return (
        f"{first} {last}\n{email}\nBachelor of Science in Information Technology\n"
        "Angeles University Foundation\nSoftware Tester, Example Studio, 2024-Present\nSkills: Testing\n"
    ).encode()


def survey(**overrides):
    payload = {
        "first_name": "QA",
        "last_name": "Case",
        "degree": "Bachelor of Science in Information Technology",
        "year_graduated": "2024",
        "ever_employed": "Yes",
        "is_currently_employed": "Yes",
        "present_job_is_first": "Yes",
        "first_occ": "QA Analyst Contract",
        "first_emp": "Example Studio",
        "first_related": "Yes",
        "first_stat": "Contractual",
        "pres_occ": "QA Analyst Contract",
        "skills": ["Testing"],
    }
    payload.update(overrides)
    return payload


results = []


def record(case_id, status, actual, data=""):
    results.append({"id": case_id, "status": status, "actual": actual, "data": data})
    print(case_id, status)
    print(" ", actual[:300].replace("\n", " "))


acode, abody = login(*ADMIN)
admin_token = abody.get("access_token", "") if isinstance(abody, dict) else ""
admin_id = (abody.get("user") or {}).get("id") if isinstance(abody, dict) else None
if not admin_token:
    raise SystemExit(f"admin login failed {acode} {detail(abody)}")

match_email = f"qa.match.{STAMP}@example.com"
ccode, cbody = call(
    "POST",
    "/api/admin/university-records",
    headers=auth(admin_token),
    json_body={
        "student_id": f"QA-{STAMP[:6]}",
        "first_name": "Match",
        "middle_name": "",
        "last_name": "Case",
        "personal_email": match_email,
        "degree": "Bachelor of Science in Information Technology",
        "year_graduated": "2024",
        "course_code": "BSIT",
        "college": "College of Computer Studies",
    },
)
record("PREP-REGISTRY", "Pass" if ccode == 200 else "Fail", f"HTTP {ccode} {detail(cbody)}", match_email)

mcode, mbody = register(match_email, resume("Match", "Case", match_email))
matched = mbody.get("matched_record") if isinstance(mbody, dict) else {}
student = (matched or {}).get("student_id") or (matched or {}).get("student_number")
record(
    "TC-REG-008",
    "Pass" if mcode == 200 and student else "Fail",
    f"HTTP {mcode}; matched={matched}",
    match_email,
)

token = mbody.get("registration_token") if isinstance(mbody, dict) else ""
blank = survey(registration_token=token, pres_occ="", first_occ="")
bcode, bbody = call("POST", "/api/auth/register/complete", json_body=blank)
scode, sbody = call("GET", "/api/admin/survey", headers=auth(admin_token))
record(
    "TC-GTS-001",
    "Pass" if bcode == 400 and scode == 404 else "Fail",
    f"blank occupation HTTP {bcode} {detail(bbody)}; GET /api/admin/survey HTTP {scode}",
    match_email,
)

good = survey(registration_token=token)
gcode, gbody = call("POST", "/api/auth/register/complete", json_body=good)
user = gbody.get("user") or {} if isinstance(gbody, dict) else {}
account_id = user.get("id")
tcode, tbody = call("GET", f"/api/admin/tracer?email={match_email}", headers=auth(admin_token))
seen = "QA Analyst Contract" in json.dumps(tbody)
lcode, lbody = login(match_email, "Alumni@2026")
login_status = ((lbody.get("user") or {}).get("status") if isinstance(lbody, dict) else None)
record(
    "TC-GTS-002",
    "Pass" if gcode == 200 and user.get("status") == "Pending" and seen and login_status == "Pending" else "Fail",
    f"complete HTTP {gcode} status={user.get('status')} id={account_id}; login HTTP {lcode} status={login_status}; tracer occupation present={seen}",
    match_email,
)

pcode, pbody = call("POST", f"/api/admin/approvals/{account_id}/approve", headers=auth(admin_token))
l2, b2 = login(match_email, "Alumni@2026")
status2 = ((b2.get("user") or {}).get("status") if isinstance(b2, dict) else None)
record(
    "TC-APR-001",
    "Pass" if pcode == 200 and status2 == "Active" else "Fail",
    f"approve HTTP {pcode} {detail(pbody)[:100]}; login status={status2}",
    match_email,
)

reject_email = f"qa.reject.{STAMP}@example.com"
rcode, rbody = register(reject_email, resume("Reject", "Case", reject_email))
rtoken = rbody.get("registration_token") if isinstance(rbody, dict) else ""
ccode, cbody = call(
    "POST",
    "/api/auth/register/complete",
    json_body=survey(registration_token=rtoken, first_name="Reject", last_name="Case", pres_occ="Clerk", first_occ="Clerk"),
)
reject_id = (cbody.get("user") or {}).get("id") if isinstance(cbody, dict) else None
empty_code, empty_body = call(
    "POST", f"/api/admin/approvals/{reject_id}/reject", headers=auth(admin_token), json_body={"reason": ""}
)
short_code, short_body = call(
    "POST", f"/api/admin/approvals/{reject_id}/reject", headers=auth(admin_token), json_body={"reason": "No"}
)
reason = "Registry identity could not be confirmed."
ok_code, ok_body = call(
    "POST", f"/api/admin/approvals/{reject_id}/reject", headers=auth(admin_token), json_body={"reason": reason}
)
l3, b3 = login(reject_email, "Alumni@2026")
user3 = b3.get("user") or {} if isinstance(b3, dict) else {}
record(
    "TC-APR-002",
    "Pass" if empty_code >= 400 and short_code >= 400 and ok_code == 200 and user3.get("status") == "Rejected" else "Fail",
    f"complete HTTP {ccode}; empty HTTP {empty_code} {detail(empty_body)[:90]}; short HTTP {short_code} {detail(short_body)[:90]}; reject HTTP {ok_code}; login status={user3.get('status')} reason={user3.get('rejection_reason')}",
    reject_email,
)

dcode, dbody = call("POST", f"/api/admin/users/{admin_id}/deactivate", headers=auth(admin_token))
l4, b4 = login(*ADMIN)
record(
    "TC-APR-003",
    "Pass" if dcode == 400 and l4 == 200 else "Fail",
    f"deactivate HTTP {dcode} {detail(dbody)}; subsequent login HTTP {l4}",
    "signed-in Super Admin",
)

# Limited admin
acode, abody = login(*ADMIN)
admin_token = abody.get("access_token")
limited_email = f"qa.admin.{STAMP}@example.com"
ucode, ubody = call(
    "POST",
    "/api/admin/users",
    headers=auth(admin_token),
    json_body={
        "first_name": "Limited",
        "last_name": "Admin",
        "email": limited_email,
        "employee_number": STAMP[:6].upper(),
        "role": "Admin",
        "status": "Active",
        "confirm": True,
    },
)
temp = ubody.get("temporary_password") if isinstance(ubody, dict) else ""
lcode, lbody = login(limited_email, temp or "missing")
ltoken = lbody.get("access_token") if isinstance(lbody, dict) else ""
privileges = (lbody.get("user") or {}).get("admin_privileges") if isinstance(lbody, dict) else None
full_admin = (lbody.get("user") or {}).get("full_admin") if isinstance(lbody, dict) else None
approvals_code, approvals_body = call("GET", "/api/admin/approvals", headers=auth(ltoken))
users_code, users_body = call("GET", "/api/admin/users", headers=auth(ltoken))
super_approvals, _ = call("GET", "/api/admin/approvals", headers=auth(admin_token))
record(
    "TC-AUTH-002",
    "Pass" if lcode == 200 and full_admin is False and approvals_code == 403 and users_code == 200 and super_approvals == 200 else "Fail",
    f"create HTTP {ucode}; login HTTP {lcode} privileges={privileges} full_admin={full_admin} must_change={(lbody.get('user') or {}).get('must_change_password') if isinstance(lbody, dict) else None}; approvals HTTP {approvals_code} {detail(approvals_body)[:80]}; users HTTP {users_code}; super approvals HTTP {super_approvals}",
    limited_email,
)

inactive_email = f"qa.inactive.{STAMP}@example.com"
icode, ibody = call(
    "POST",
    "/api/admin/users",
    headers=auth(admin_token),
    json_body={
        "first_name": "Inactive",
        "last_name": "Admin",
        "email": inactive_email,
        "employee_number": STAMP[2:8].upper(),
        "role": "Admin",
        "status": "Inactive",
        "confirm": True,
    },
)
itemp = ibody.get("temporary_password") if isinstance(ibody, dict) else ""
ncode, nbody = login(inactive_email, itemp or "missing")
created_priv = ((ibody.get("item") or {}).get("admin_privileges") if isinstance(ibody, dict) else None)
record(
    "TC-AUTH-003",
    "Blocked",
    f"Created account is an Admin with privileges={created_priv}, not a second Super Admin. Inactive login HTTP {ncode} {detail(nbody)}. The only Super Admin was not deactivated.",
    inactive_email,
)

# Maria wrong password then correct
messages = []
for _ in range(3):
    code, body = login(MARIA[0], "WrongPass1")
    messages.append(f"{code}:{detail(body)}")
ok_code, ok_body = login(*MARIA)
maria_token = ok_body.get("access_token") if isinstance(ok_body, dict) else ""
maria_status = ((ok_body.get("user") or {}).get("status") if isinstance(ok_body, dict) else None)
record(
    "TC-AUTH-001",
    "Pass" if messages == ["401:Incorrect email or password."] * 3 and ok_code == 200 and maria_status == "Active" else "Fail",
    f"attempts={messages}; correct HTTP {ok_code} status={maria_status}",
    MARIA[0],
)

# Alignment before and after a non-current job title edit, then restore
before_code, before = call("GET", "/api/admin/tracer?email=maria.reyes@gmail.com", headers=auth(admin_token))
before_items = before.get("items") if isinstance(before, dict) else []
before_alignment = before_items[0].get("alignment") if before_items else None
jcode, jobs = call("GET", "/api/alumni/jobs", headers=auth(maria_token))
job_list = jobs.get("jobs") if isinstance(jobs, dict) else []
target = next((job for job in job_list if not job.get("is_current")), job_list[-1] if job_list else None)
if target:
    original = target.get("job_title")
    put_code, put_body = call(
        "PUT",
        f"/api/alumni/jobs/{target.get('id')}",
        headers=auth(maria_token),
        json_body={
            "job_title": "Bookstore Clerk",
            "company": target.get("company") or "Example",
            "is_current": bool(target.get("is_current")),
            "start_date": target.get("start_date"),
            "end_date": target.get("end_date"),
        },
    )
    after_code, after = call("GET", "/api/admin/tracer?email=maria.reyes@gmail.com", headers=auth(admin_token))
    after_items = after.get("items") if isinstance(after, dict) else []
    after_alignment = after_items[0].get("alignment") if after_items else None
    restore_code, _ = call(
        "PUT",
        f"/api/alumni/jobs/{target.get('id')}",
        headers=auth(maria_token),
        json_body={
            "job_title": original,
            "company": target.get("company") or "Example",
            "is_current": bool(target.get("is_current")),
            "start_date": target.get("start_date"),
            "end_date": target.get("end_date"),
        },
    )
    record(
        "TC-ALN-001",
        "Pass" if put_code == 200 and before_alignment and before_alignment == after_alignment and restore_code == 200 else "Fail",
        f"jobs HTTP {jcode} count={len(job_list)}; edited job {target.get('id')} current={target.get('is_current')} HTTP {put_code}; alignment {before_alignment} -> {after_alignment}; restored HTTP {restore_code}",
        "Bookstore Clerk",
    )
else:
    record("TC-ALN-001", "Blocked", f"jobs HTTP {jcode} {detail(jobs)[:120]}", MARIA[0])

# PIN lock. Email delivery is disabled in this environment.
pcode, pbody = call("POST", "/api/auth/forgot-password", json_body={"email": MARIA[0]})
pin_messages = []
for n in range(1, 6):
    vcode, vbody = call("POST", "/api/auth/forgot-password/verify", json_body={"email": MARIA[0], "pin": "000000"})
    pin_messages.append(f"{n}:{vcode}:{detail(vbody)}")
four_open = all(item.startswith(f"{n}:400:The PIN is incorrect") for n, item in enumerate(pin_messages[:4], start=1))
fifth_locked = pin_messages[-1].startswith("5:400:Too many incorrect attempts")
record(
    "TC-PWD-001",
    "Pass" if pcode == 200 and four_open and fifth_locked else "Blocked" if pcode != 200 else "Fail",
    f"request HTTP {pcode} {detail(pbody)}; email_enabled=false so delivery was not observed; attempts={pin_messages}",
    "PIN 000000",
)

# QR display does not add a usage row
q1, before_activity = call(
    "GET", "/api/admin/partner-activity?q=maria.reyes@gmail.com&page_size=50", headers=auth(admin_token)
)
before_total = before_activity.get("total") if isinstance(before_activity, dict) else None
qr_code, qr_body = call("GET", "/api/alumni/qr", headers=auth(maria_token))
img_code, img_body = call("GET", "/api/alumni/qr/image", headers=auth(maria_token))
q2, after_activity = call(
    "GET", "/api/admin/partner-activity?q=maria.reyes@gmail.com&page_size=50", headers=auth(admin_token)
)
after_total = after_activity.get("total") if isinstance(after_activity, dict) else None
identity = {key: qr_body.get(key) for key in ("student_number", "student_id", "name", "course", "college", "year", "year_graduated") if isinstance(qr_body, dict)}
record(
    "TC-QR-001",
    "Pass" if qr_code == 200 and img_code == 200 and before_total == after_total and any(identity.values()) else "Fail",
    f"usage {before_total} -> {after_total}; identity HTTP {qr_code} {identity}; image HTTP {img_code}",
    MARIA[0],
)

OUT.write_text(json.dumps({"stamp": STAMP, "results": results}, indent=2), encoding="utf-8")
print("SAVED", OUT)
