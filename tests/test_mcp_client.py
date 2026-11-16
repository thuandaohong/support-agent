"""Test MCP client (tools/mcp_client.py) — HTTP thay bằng hàm giả, response lấy đúng dạng Gateway trả
khi gọi thật (Day 60 bước 4). Không gọi AWS, chạy trên CI.
"""
import json

import pytest
from botocore.credentials import Credentials

from tools import mcp_client
from tools.mcp_client import GatewayError

URL = "https://gw-test.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"


class FakeResp:
    def __init__(self, status=200, body=None, content_type="application/json"):
        self.status = status
        self.data = (body if isinstance(body, str) else json.dumps(body)).encode()
        self.headers = {"Content-Type": content_type}


class FakeHttp:
    def __init__(self, resp):
        self.resp = resp
        self.sent = []

    def request(self, method, url, body, headers, timeout):
        self.sent.append({"method": method, "url": url, "body": json.loads(body), "headers": headers})
        if isinstance(self.resp, Exception):
            raise self.resp
        return self.resp


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setattr(mcp_client, "_credentials", lambda: Credentials("AKIDTEST", "secret"))

    def install(resp):
        fake = FakeHttp(resp)
        monkeypatch.setattr(mcp_client, "_http", fake)
        return fake
    return install


def tool_result(payload, is_error=False):
    return {"jsonrpc": "2.0", "id": 1,
            "result": {"isError": is_error, "content": [{"type": "text", "text": json.dumps(payload)}]}}


def test_call_tool_signs_request_and_unwraps_lambda_json(http):
    fake = http(FakeResp(body=tool_result({"found": True, "order": {"plan": "Premium"}})))
    out = mcp_client.call_tool(URL, "orders___get_order", {"order_id": "1003", "customer_id": "C003"})
    assert out == {"found": True, "order": {"plan": "Premium"}}

    sent = fake.sent[0]
    assert sent["method"] == "POST" and sent["url"] == URL
    assert sent["body"]["method"] == "tools/call"
    assert sent["body"]["params"] == {"name": "orders___get_order",
                                      "arguments": {"order_id": "1003", "customer_id": "C003"}}
    auth = sent["headers"]["Authorization"]
    assert auth.startswith("AWS4-HMAC-SHA256") and "/us-east-1/bedrock-agentcore/aws4_request" in auth


def test_list_tools(http):
    http(FakeResp(body={"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": "orders___get_order"}]}}))
    assert [t["name"] for t in mcp_client.list_tools(URL)] == ["orders___get_order"]


def test_parses_sse_response(http):
    sse = "event: message\ndata: " + json.dumps(tool_result({"found": False})) + "\n\n"
    http(FakeResp(body=sse, content_type="text/event-stream"))
    assert mcp_client.call_tool(URL, "orders___get_order", {}) == {"found": False}


@pytest.mark.parametrize("resp, code", [
    (FakeResp(status=401, body={"jsonrpc": "2.0", "id": 1, "error": {"code": -32001}}), "http_401"),
    (FakeResp(status=403, body="{}"), "http_403"),
    (FakeResp(body={"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Unknown tool"}}), "rpc_-32602"),
    (FakeResp(body=tool_result("ValidationException - Missing required field", is_error=True)), "tool_rejected"),
    (FakeResp(body=tool_result({"error": "invalid_input"})), "tool_invalid_input"),   # Lambda báo lỗi, isError=false
    (FakeResp(body={"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "không phải JSON"}]}}),
     "tool_bad_output"),
    (FakeResp(body="<html>502</html>"), "bad_response"),
])
def test_every_failure_becomes_short_gateway_error(http, resp, code):
    http(resp)
    with pytest.raises(GatewayError) as e:
        mcp_client.call_tool(URL, "orders___get_order", {"order_id": "1003", "customer_id": "C003"})
    assert str(e.value) == code


def test_network_failure_is_gateway_error(http):
    import urllib3
    http(urllib3.exceptions.ReadTimeoutError(None, URL, "timed out"))
    with pytest.raises(GatewayError, match="unreachable"):
        mcp_client.call_tool(URL, "orders___get_order", {})


def test_concurrent_calls_get_distinct_ids(http):
    # policy_node và order_node chạy SONG SONG (LangGraph dùng thread pool) → 2 lời gọi Gateway cùng
    # lúc từ 2 thread, chung _http và _ids. Mỗi request phải có id riêng, không lẫn kết quả.
    from concurrent.futures import ThreadPoolExecutor
    fake = http(FakeResp(body=tool_result({"found": False})))
    with ThreadPoolExecutor(max_workers=8) as pool:
        outs = list(pool.map(lambda _: mcp_client.call_tool(URL, "orders___get_order", {}), range(64)))
    assert outs == [{"found": False}] * 64
    ids = [s["body"]["id"] for s in fake.sent]
    assert len(ids) == len(set(ids)) == 64


def test_pool_keeps_connections_for_parallel_nodes():
    # Mặc định urllib3 giữ 1 kết nối/host → 2 node song song làm mất keep-alive (đo thật Day 61)
    assert mcp_client._http.connection_pool_kw["maxsize"] >= 2
