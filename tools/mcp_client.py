"""MCP client tối giản cho AgentCore Gateway (Day 60): tools/list, tools/call qua HTTPS + SigV4.

Không dùng thư viện `mcp` — Gateway inbound AWS_IAM, đã kiểm thật (Day 60 bước 4):
- tools/list, tools/call chạy KHÔNG cần initialize trước; không cấp Mcp-Session-Id → mỗi request độc lập
- response là JSON thường (không SSE), dù Accept có text/event-stream; vẫn đỡ SSE phòng khi đổi
- ký SigV4 với service "bedrock-agentcore"; không ký → 401 (JSON-RPC -32001)
- kết quả tool nằm trong result.content[].text (chuỗi JSON của Lambda), isError=false
- Gateway tự kiểm inputSchema: thiếu trường → isError=true, Lambda không được gọi
- tool không tồn tại → JSON-RPC error -32602

Mọi lỗi (mạng, HTTP, JSON-RPC, tool) → GatewayError với mã ngắn, KHÔNG kèm nội dung đơn/câu hỏi.

HTTP bằng urllib3 (có sẵn — botocore phụ thuộc nó): giữ kết nối TLS để dùng lại giữa các lời gọi.
Đo từ máy dev (VN → us-east-1): mở kết nối mới ~500ms/lần (TCP + TLS), Lambda chỉ 6–34ms.

Chạy thử: python scripts/mcp_call.py
"""
from __future__ import annotations

import itertools
import json
import os

import boto3
import urllib3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

REGION = os.environ.get("AWS_REGION", "us-east-1")
SERVICE = "bedrock-agentcore"
TIMEOUT = 10  # giây — tra 1 đơn: cold start Lambda ~1s; hơn 10s thì coi như Gateway hỏng

_session = boto3.Session()
# retries=False: không tự retry — tools/call không chắc idempotent ở mọi tool.
# maxsize=4: số kết nối giữ lại cho MỖI host. Mặc định 1 → policy_node + order_node gọi Gateway song
# song (Day 61) thì 1 kết nối bị vứt sau mỗi lượt ("Connection pool is full, discarding connection"),
# lần sau phải bắt tay TLS lại. 2 node song song là đủ; dư một chút cho an toàn.
_http = urllib3.PoolManager(retries=False, maxsize=4)
_ids = itertools.count(1)


class GatewayError(Exception):
    """Gọi tool qua Gateway thất bại. str(e) là mã ngắn (vd http_403, rpc_-32602, tool_invalid_input)."""


def _credentials():
    # Mỗi lần gọi lấy lại: credentials của role Runtime/Lambda là tạm thời, boto3 tự làm mới
    return _session.get_credentials().get_frozen_credentials()


def rpc(url: str, method: str, params: dict | None = None, timeout: float = TIMEOUT) -> dict:
    """Gửi 1 request JSON-RPC đã ký SigV4, trả về `result`."""
    msg = {"jsonrpc": "2.0", "id": next(_ids), "method": method}
    if params is not None:
        msg["params"] = params
    body = json.dumps(msg, ensure_ascii=False).encode()
    req = AWSRequest(method="POST", url=url, data=body,
                     headers={"Content-Type": "application/json",
                              "Accept": "application/json, text/event-stream"})
    SigV4Auth(_credentials(), SERVICE, REGION).add_auth(req)
    try:
        resp = _http.request("POST", url, body=body, headers=dict(req.headers),
                             timeout=urllib3.Timeout(total=timeout))
    except urllib3.exceptions.HTTPError as e:      # gồm timeout, không kết nối được
        raise GatewayError("unreachable") from e
    if resp.status != 200:
        raise GatewayError(f"http_{resp.status}")
    try:
        reply = _parse(resp.data.decode(), resp.headers.get("Content-Type", ""))
    except json.JSONDecodeError:
        raise GatewayError("bad_response") from None
    if "error" in reply:
        raise GatewayError(f"rpc_{reply['error'].get('code')}")
    return reply["result"]


def _parse(payload: str, content_type: str) -> dict:
    if content_type.startswith("text/event-stream"):
        data = [line[5:].strip() for line in payload.splitlines() if line.startswith("data:")]
        payload = data[-1] if data else "{}"
    return json.loads(payload)


def list_tools(url: str) -> list[dict]:
    return rpc(url, "tools/list")["tools"]


def call_tool(url: str, name: str, arguments: dict, timeout: float = TIMEOUT) -> dict:
    """Gọi 1 tool, trả về dict Lambda trả. Lỗi phía tool → GatewayError."""
    result = rpc(url, "tools/call", {"name": name, "arguments": arguments}, timeout)
    if result.get("isError"):
        raise GatewayError("tool_rejected")      # vd Gateway chặn vì sai inputSchema
    text = "".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise GatewayError("tool_bad_output") from None
    if isinstance(data, dict) and "error" in data:   # Lambda tự báo lỗi (isError vẫn false)
        raise GatewayError(f"tool_{data['error']}")
    return data
