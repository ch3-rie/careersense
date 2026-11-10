"""Retest administrator access after the first attempt used an invalid employee number."""

import json
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API = "http://127.0.0.1:8000"
OUT = Path(__file__).with_name("execution-results-auth.json")


def call(method, path, *, headers=None, json_body=None):
    body = None
    hdrs = dict(headers or {})
    if json_body is not None:
        body = json.dumps(json_body).encode()
        hdrs["Content-Type"] = "application/json"
    req = Request(API + path, data=body, headers=hdrs, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "null")
    except HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw[:300]}
        return exc.code, payload


def detail(payload):
    item = payload.get("detail", payload) if isinstance(payload, dict) else payload
    if isinstance(item, list):
        return "; ".join(str(part.get("msg", part)) for part in item)
    return str(item)


code, body = call("POST", "/api/auth/login", json_body={"email": "admin@auf.edu.ph", "password": "Admin@AUF2026"})
token = body.get("access_token")
headers = {"Authorization": f"Bearer {token}"}
stamp = uuid.uuid4().hex[:6]
limited = f"qa.admin.{stamp}@example.com"
inactive = f"qa.inactive.{stamp}@example.com"

lcode, lbody = call(
    "POST",
    "/api/admin/users",
    headers=headers,
    json_body={
        "first_name": "Limited",
        "last_name": "Admin",
        "email": limited,
        "employee_number": "091",
        "role": "Admin",
        "status": "Active",
        "confirm": True,
    },
)
temp = lbody.get("temporary_password") if isinstance(lbody, dict) else ""
scode, sbody = call("POST", "/api/auth/login", json_body={"email": limited, "password": temp})
stoken = sbody.get("access_token") if isinstance(sbody, dict) else ""
user = sbody.get("user") or {} if isinstance(sbody, dict) else {}
aheaders = {"Authorization": f"Bearer {stoken}"}
approvals, abody = call("GET", "/api/admin/approvals", headers=aheaders)
users, ubody = call("GET", "/api/admin/users", headers=aheaders)
tracer, _ = call("GET", "/api/admin/tracer", headers=aheaders)
account, _ = call("GET", "/api/auth/me", headers=aheaders)

icode, ibody = call(
    "POST",
    "/api/admin/users",
    headers=headers,
    json_body={
        "first_name": "Inactive",
        "last_name": "Admin",
        "email": inactive,
        "employee_number": "092",
        "role": "Admin",
        "status": "Inactive",
        "confirm": True,
    },
)
itemp = ibody.get("temporary_password") if isinstance(ibody, dict) else ""
ncode, nbody = call("POST", "/api/auth/login", json_body={"email": inactive, "password": itemp})

report = {
    "limited_email": limited,
    "create_limited": lcode,
    "create_detail": detail(lbody)[:160],
    "privileges": (lbody.get("item") or {}).get("admin_privileges") if isinstance(lbody, dict) else None,
    "login": scode,
    "full_admin": user.get("full_admin"),
    "must_change_password": user.get("must_change_password"),
    "approvals": [approvals, detail(abody)[:120]],
    "users": users,
    "tracer": tracer,
    "me": account,
    "inactive_email": inactive,
    "create_inactive": icode,
    "inactive_privileges": (ibody.get("item") or {}).get("admin_privileges") if isinstance(ibody, dict) else None,
    "inactive_login": [ncode, detail(nbody)[:160]],
}
OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if "password" not in k}, indent=2))
