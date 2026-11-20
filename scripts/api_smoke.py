"""Smoke test web API thật (Day 64): CORS, 401/403, scope, customer_id từ token, nhớ hội thoại, throttle.

Đóng vai trình duyệt: đăng nhập user test Cognito (auth/cognito.py, infra/auth/test-users.env) rồi
gọi POST /chat của HTTP API (tra URL theo tên). Chỉ 3 ca chạm tới agent (tốn Bedrock); các ca bị
chặn dừng ở HTTP API hoặc Bridge.

Chạy:  python scripts/api_smoke.py            (lỗi kỳ vọng → exit 1)
       python scripts/api_smoke.py --throttle (thêm ca bắn 150 request nhanh — bị Bridge chặn, không tốn Bedrock)
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
import urllib3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from auth.cognito import Cognito

REGION = os.environ.get("AWS_REGION", "us-east-1")
API_NAME = os.environ.get("API_NAME", "support-chat-api")
ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:5173")
http = urllib3.PoolManager(maxsize=32, timeout=urllib3.Timeout(connect=5, read=35), retries=False)


def api_url() -> str:
    for a in boto3.client("apigatewayv2", region_name=REGION).get_apis()["Items"]:
        if a["Name"] == API_NAME:
            return a["ApiEndpoint"] + "/chat"
    sys.exit(f"Không thấy HTTP API {API_NAME} — Terraform tạo (infra/terraform, modules/web_api)")


def post(url, body, token=None, raw_auth=None):
    headers = {"content-type": "application/json", "origin": ORIGIN}
    if token:
        headers["authorization"] = f"Bearer {token}"
    if raw_auth:
        headers["authorization"] = raw_auth
    r = http.request("POST", url, body=json.dumps(body, ensure_ascii=False).encode(), headers=headers)
    try:
        data = json.loads(r.data or b"{}")
    except ValueError:
        data = {}
    return r.status, data


def preflight(url, origin):
    r = http.request("OPTIONS", url, headers={
        "origin": origin, "access-control-request-method": "POST",
        "access-control-request-headers": "authorization,content-type"})
    return r.status, r.headers.get("access-control-allow-origin")


def tamper(token: str) -> str:
    """Đổi username trong payload sang khách khác, giữ chữ ký cũ."""
    header, payload, sig = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["username"] = "c020"
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{header}.{forged}.{sig}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--throttle", action="store_true", help="thêm ca 150 request nhanh (bị Bridge chặn 400, không tốn Bedrock)")
    args = parser.parse_args()

    url = api_url()
    cognito = Cognito()
    c003, c020 = cognito.login("C003"), cognito.login("C020")
    q = {"question": "Đơn #1003 còn đổi trả được không?", "session_id": str(uuid.uuid4())}
    results = []

    def check(name, ok, detail):
        results.append(ok)
        print(f"{'✅' if ok else '❌'} {name:<46} {detail}")

    status, allow = preflight(url, ORIGIN)
    check("preflight từ origin được phép", status == 204 and allow == ORIGIN, f"{status} allow-origin={allow}")
    status, allow = preflight(url, "https://evil.example")
    check("preflight từ origin lạ", allow is None, f"{status} allow-origin={allow}")

    status, _ = post(url, q)
    check("không token", status == 401, status)
    status, _ = post(url, q, raw_auth="Bearer abc.def.ghi")
    check("token rác", status == 401, status)
    status, _ = post(url, q, token=tamper(c003["AccessToken"]))
    check("token bị sửa username (c003 → c020)", status == 401, status)
    status, _ = post(url, q, token=c003["IdToken"])
    check("ID token (không có scope)", status == 403, status)
    status, body = post(url, {**q, "customer_id": "C020"}, token=c003["AccessToken"])
    check("body tự khai customer_id", status == 400 and body.get("error") == "unexpected_field", f"{status} {body}")

    status, body = post(url, q, token=c003["AccessToken"])
    check("C003 hỏi #1003", status == 200 and "orders/1003" in body.get("sources", []),
          f"{status} route={body.get('route')} sources={body.get('sources')}")
    status, body = post(url, {"question": "Thế bảo hành thì sao?", "session_id": q["session_id"]},
                        token=c003["AccessToken"])
    check("C003 lượt 2 cùng session (nhớ #1003)", status == 200 and "orders/1003" in body.get("sources", []),
          f"{status} route={body.get('route')} sources={body.get('sources')}")
    status, body = post(url, q, token=c020["AccessToken"])   # dùng LẠI session_id của C003
    check("C020 hỏi #1003 (dùng lại session của C003)", status == 200 and "orders/1003" not in body.get("sources", []),
          f"{status} route={body.get('route')} sources={body.get('sources')}")

    if args.throttle:
        # Đo thật Day 64: request KHÔNG token bị authorizer trả 401 và KHÔNG bị throttle đếm (100 → 100×401);
        # throttle chỉ áp cho request đã qua authorizer. Dùng token thật + body có customer_id → Bridge
        # trả 400 ngay, không gọi Runtime → không tốn Bedrock. 25 luồng ≈ 60 req/s.
        bad = {**q, "customer_id": "C020"}
        with ThreadPoolExecutor(25) as pool:
            codes = list(pool.map(lambda _: post(url, bad, token=c003["AccessToken"])[0], range(150)))
        counts = {c: codes.count(c) for c in sorted(set(codes))}
        check("150 request nhanh (đã đăng nhập)", 429 in counts, counts)

    print(f"\n{sum(results)}/{len(results)} đúng kỳ vọng")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
