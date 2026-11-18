"""Bridge Lambda — cầu giữa HTTP API (web) và AgentCore Runtime (Day 64).

Vì sao cần: Runtime xác thực IAM (SigV4). Trình duyệt KHÔNG được giữ AWS key, và HTTP API không có
integration gọi thẳng InvokeAgentRuntime → Lambda này (có IAM role) gọi thay khách.

Trước khi tới đây, HTTP API đã: throttle, kiểm chữ ký / iss / client / exp của access token Cognito
(JWT authorizer) và bắt buộc scope aws.cognito.signin.user.admin. Lambda đọc claims đã kiểm ở
event["requestContext"]["authorizer"]["jwt"]["claims"] (payload format 2.0) rồi:
  1. customer_id = username.upper() — CHỈ từ claims, không bao giờ từ body. Kiểm lại
     token_use == "access": JWT authorizer không phân biệt access/ID token (AWS docs), scope là
     lớp chặn chính, đây là lớp phòng hờ khi cấu hình route bị sửa nhầm
  2. body chỉ được có {question, session_id}: trường lạ (vd customer_id) → 400
  3. runtimeSessionId = "web-" + sha256(customer_id:session_id) — Runtime chọn microVM theo id này
     và KHÔNG kiểm session thuộc khách nào → băm kèm khách: khách khác gửi lại đúng session_id
     của người khác vẫn ra id khác, không chung microVM / RAM. Cùng khách + cùng tab → cùng id →
     agent nhớ hội thoại (Day 62)
  4. gọi Runtime: timeout đọc 25 s (HTTP API cắt ở 30 s), KHÔNG retry — retry = hỏi Bedrock 2 lần
  5. trả {answer, sources, route, error?}; Runtime lỗi / quá hạn → 502 agent_unavailable

Log: mã kết quả, độ dài câu hỏi, thời gian. KHÔNG log câu hỏi, câu trả lời, token, customer_id.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import time

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

log = logging.getLogger()
log.setLevel(logging.INFO)

RUNTIME_ARN = os.environ["AGENT_RUNTIME_ARN"]   # thiếu thì lỗi ngay lúc init (fail fast)
MAX_QUESTION = 2000                             # giống serve.py
MAX_BODY = 8192
FIELDS = {"question", "session_id"}
PUBLIC = ("answer", "sources", "route", "error")   # không trả order_lookup / steps (nội bộ)
_CUSTOMER_ID = re.compile(r"^C\d{3,6}$")
_SESSION_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")   # crypto.randomUUID()

_client = boto3.client("bedrock-agentcore", config=Config(
    connect_timeout=5, read_timeout=25, retries={"total_max_attempts": 1}))


class Rejected(Exception):
    """Request không hợp lệ: status HTTP + mã ngắn trả cho trình duyệt (không kèm nội dung)."""

    def __init__(self, status: int, reason: str):
        super().__init__(reason)
        self.status, self.reason = status, reason


def respond(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, ensure_ascii=False)}


def customer_from_claims(event: dict) -> str:
    claims = (((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt") or {}).get("claims")
    if not claims:            # route không gắn authorizer → không bao giờ được chạy tiếp
        raise Rejected(403, "no_claims")
    if claims.get("token_use") != "access":
        raise Rejected(403, "not_access_token")
    customer = str(claims.get("username", "")).upper()   # pool không phân biệt hoa/thường: "c003"
    if not _CUSTOMER_ID.fullmatch(customer):
        raise Rejected(403, "bad_customer_id")
    return customer


def parse_body(event: dict) -> tuple[str, str]:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8", "replace")
    if len(raw) > MAX_BODY:
        raise Rejected(400, "body_too_large")
    try:
        body = json.loads(raw)
    except ValueError:
        raise Rejected(400, "invalid_json") from None
    if not isinstance(body, dict):
        raise Rejected(400, "invalid_json")
    if set(body) - FIELDS:    # vd {"customer_id": "C020"} — danh tính chỉ đến từ token
        raise Rejected(400, "unexpected_field")
    question = body.get("question")
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= MAX_QUESTION:
        raise Rejected(400, "invalid_question")
    session_id = body.get("session_id")
    if not isinstance(session_id, str) or not _SESSION_ID.fullmatch(session_id):
        raise Rejected(400, "invalid_session_id")
    return question.strip(), session_id


def runtime_session(customer_id: str, session_id: str) -> str:
    return "web-" + hashlib.sha256(f"{customer_id}:{session_id}".encode()).hexdigest()   # 68 ký tự ≥ 33


def ask_agent(session: str, question: str, customer_id: str) -> dict:
    resp = _client.invoke_agent_runtime(
        agentRuntimeArn=RUNTIME_ARN,
        qualifier="DEFAULT",
        runtimeSessionId=session,
        contentType="application/json",
        accept="application/json",
        payload=json.dumps({"question": question, "customer_id": customer_id}, ensure_ascii=False),
    )
    out = json.loads(resp["response"].read())
    if not isinstance(out, dict) or "answer" not in out:   # vd container trả {"error": "internal_error"}
        raise ValueError("bad_agent_output")
    return out


def lambda_handler(event, context):
    t0 = time.perf_counter()
    try:
        customer_id = customer_from_claims(event)
        question, session_id = parse_body(event)
    except Rejected as e:
        log.warning("chat rejected status=%d reason=%s", e.status, e.reason)
        return respond(e.status, {"error": e.reason})

    try:
        out = ask_agent(runtime_session(customer_id, session_id), question, customer_id)
    except (ClientError, BotoCoreError, ValueError) as e:
        cause = e.response["Error"]["Code"] if isinstance(e, ClientError) else type(e).__name__
        log.warning("chat agent_unavailable cause=%s ms=%d", cause, (time.perf_counter() - t0) * 1000)
        return respond(502, {"error": "agent_unavailable"})

    log.info("chat ok q_len=%d ms=%d", len(question), (time.perf_counter() - t0) * 1000)
    return respond(200, {k: out[k] for k in PUBLIC if k in out})
