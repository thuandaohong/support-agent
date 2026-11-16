"""Test Lambda search_policy (Day 61) — client Bedrock KB thay bằng hàm giả, context giả như Gateway gửi.

Không gọi AWS, chạy trên CI. Định dạng retrievalResults lấy đúng như API retrieve trả.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from lambdas.search_policy import handler

SCHEMA = Path(__file__).resolve().parent.parent / "infra" / "gateway" / "search_policy.tool.json"
URI = "s3://b/policies/"
RESULTS = [{"content": {"text": f"đoạn {i}"}, "location": {"s3Location": {"uri": f"{URI}0{i}.md"}},
            "score": 0.9 - i / 10} for i in range(1, 6)]   # KB trả mặc định 5 đoạn


class FakeKB:
    def __init__(self, error=None):
        self.calls, self.error = [], error

    def retrieve(self, knowledgeBaseId, retrievalQuery):
        self.calls.append((knowledgeBaseId, retrievalQuery))
        if self.error:
            raise self.error
        return {"retrievalResults": RESULTS}


@pytest.fixture
def kb(monkeypatch):
    def install(error=None):
        fake = FakeKB(error)
        monkeypatch.setattr(handler, "_client", fake)
        return fake
    return install


def ctx(tool="policies___search_policy"):
    custom = {"bedrockAgentCoreToolName": tool} if tool else {}
    return SimpleNamespace(client_context=SimpleNamespace(custom=custom))


def test_returns_hits_in_search_policy_format(kb):
    fake = kb()
    out = handler.lambda_handler({"query": "  Gói Premium đổi trả mấy ngày?  "}, ctx())
    assert [h["source"] for h in out["hits"]] == [f"{URI}01.md", f"{URI}02.md", f"{URI}03.md"]  # mặc định 3
    assert set(out["hits"][0]) == {"text", "source", "score"}
    assert fake.calls == [("TEST_KB", {"text": "Gói Premium đổi trả mấy ngày?"})]   # đã strip
    json.dumps(out, ensure_ascii=False)               # Gateway phải serialize được


@pytest.mark.parametrize("top_k, n", [(1, 1), (5, 5)])
def test_top_k_cuts_results(kb, top_k, n):
    kb()
    assert len(handler.lambda_handler({"query": "đổi trả", "top_k": top_k}, ctx())["hits"]) == n


@pytest.mark.parametrize("event", [
    {}, {"query": ""}, {"query": "   "}, {"query": 123}, {"query": "x" * 2001},
    {"query": "đổi trả", "top_k": 0}, {"query": "đổi trả", "top_k": 6},
    {"query": "đổi trả", "top_k": "3"}, {"query": "đổi trả", "top_k": True},
    ["đổi trả"],
])
def test_invalid_input_never_reaches_kb(kb, event):
    fake = kb()
    assert handler.lambda_handler(event, ctx()) == {"error": "invalid_input"}
    assert fake.calls == []


@pytest.mark.parametrize("tool", ["orders___get_order", "policies___delete_policy", None])
def test_unknown_tool(kb, tool):
    fake = kb()
    assert handler.lambda_handler({"query": "đổi trả"}, ctx(tool)) == {"error": "unknown_tool"}
    assert fake.calls == []


@pytest.mark.parametrize("error", [
    ClientError({"Error": {"Code": "ThrottlingException", "Message": "slow down"}}, "Retrieve"),
    EndpointConnectionError(endpoint_url="https://bedrock-agent-runtime.us-east-1.amazonaws.com"),
])
def test_kb_failure_is_short_error_not_empty_hits(kb, error):
    kb(error)
    # KHÔNG trả {"hits": []} — rỗng nghĩa là "không có chính sách liên quan", khác hẳn "KB hỏng"
    assert handler.lambda_handler({"query": "đổi trả"}, ctx()) == {"error": "kb_unavailable"}


def test_query_not_logged(kb, caplog):
    kb()
    secret = "Tôi là Nguyễn Văn A, số điện thoại 0912345678"
    with caplog.at_level("INFO"):
        handler.lambda_handler({"query": secret}, ctx())
    assert secret not in caplog.text and "0912345678" not in caplog.text
    assert f"query_len={len(secret)}" in caplog.text


def test_schema_matches_handler():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["name"] == "search_policy"
    assert tuple(schema["inputSchema"]["required"]) == handler.REQUIRED
    props = schema["inputSchema"]["properties"]
    # Gateway CHỈ nhận type/properties/required/items/description (đo khi tạo target, Day 61):
    # maxLength/minimum/maximum bị từ chối → giới hạn ghi bằng chữ, Lambda tự kiểm
    allowed = {"type", "properties", "required", "items", "description"}
    assert all(set(p) <= allowed for p in props.values())
    assert str(handler.MAX_QUERY) in props["query"]["description"]
    assert f"1–{handler.MAX_TOP_K}" in props["top_k"]["description"]
