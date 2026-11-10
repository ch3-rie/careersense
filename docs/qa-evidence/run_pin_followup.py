import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

API = "http://127.0.0.1:8000"


def post(path, payload):
    req = Request(
        API + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


code, body = post("/api/auth/forgot-password", {"email": "maria.reyes@gmail.com"})
print("request", code, body.get("detail") or body.get("message") or body)
for n in range(1, 7):
    vcode, vbody = post("/api/auth/forgot-password/verify", {"email": "maria.reyes@gmail.com", "pin": "000000"})
    print(n, vcode, vbody.get("detail"))
