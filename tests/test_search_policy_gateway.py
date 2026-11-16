"""Test đường tra chính sách qua Gateway (Day 61): adapter tools/search_policy_gateway.py + chọn backend.

call_tool thay bằng hàm giả — không gọi AWS. Định dạng {"hits": [...]} lấy đúng như Lambda trả khi
gọi thật (scripts/mcp_call.py).
"""
import pytest

from agents import nodes
from tools.mcp_client import GatewayError

HIT = {"text": "Premium: 14 ngày", "source": "s3://b/policies/01-return-policy.md", "score": 0.57}


@pytest.fixture
def gw(monkeypatch):
    monkeypatch.setenv("GATEWAY_URL", "https://gw-test.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp")
    from tools import search_policy_gateway
    return search_policy_gateway


def test_returns_hits_like_direct_backend(gw, monkeypatch):
    sent = {}

    def fake_call(url, name, arguments):
        sent.update(name=name, arguments=arguments)
        return {"hits": [HIT]}

    monkeypatch.setattr(gw, "call_tool", fake_call)
    assert gw.search_policy("Gói Premium đổi trả mấy ngày?", top_k=2) == [HIT]
    assert sent == {"name": "policies___search_policy",
                    "arguments": {"query": "Gói Premium đổi trả mấy ngày?", "top_k": 2}}


def test_empty_hits_is_normal_not_error(gw, monkeypatch):
    monkeypatch.setattr(gw, "call_tool", lambda url, name, arguments: {"hits": []})
    assert gw.search_policy("Thủ đô của Pháp?") == []


@pytest.mark.parametrize("reply", [{}, {"hits": "không phải list"}, ["hits"]])
def test_wrong_shape_is_gateway_error(gw, monkeypatch, reply):
    monkeypatch.setattr(gw, "call_tool", lambda url, name, arguments: reply)
    with pytest.raises(GatewayError, match="tool_bad_output"):
        gw.search_policy("đổi trả")


def test_gateway_failure_is_not_swallowed(gw, monkeypatch):
    def broken(url, name, arguments):
        raise GatewayError("tool_kb_unavailable")
    monkeypatch.setattr(gw, "call_tool", broken)
    with pytest.raises(GatewayError):          # KHÔNG được biến thành [] ("không có chính sách")
        gw.search_policy("đổi trả")


def test_pick_backend(gw):
    from tools import search_policy as direct
    assert nodes._pick_search_policy("direct") is direct.search_policy
    assert nodes._pick_search_policy("gateway") is gw.search_policy
    with pytest.raises(ValueError):
        nodes._pick_search_policy("kb")
