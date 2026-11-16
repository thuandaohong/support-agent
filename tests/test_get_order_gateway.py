"""Test đường tra đơn qua Gateway (Day 60): adapter tools/get_order_gateway.py + chọn backend.

call_tool thay bằng hàm giả — không gọi AWS. Định dạng {"found", "order"} lấy đúng như Lambda trả
khi gọi thật (scripts/mcp_call.py).
"""
import pytest

from agents import nodes
from tools.mcp_client import GatewayError


@pytest.fixture
def gw(monkeypatch):
    monkeypatch.setenv("GATEWAY_URL", "https://gw-test.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp")
    from tools import get_order_gateway
    return get_order_gateway


def test_found_returns_order_like_direct_backend(gw, monkeypatch):
    sent = {}

    def fake_call(url, name, arguments):
        sent.update(url=url, name=name, arguments=arguments)
        return {"found": True, "order": {"order_id": "1003", "customer_id": "C003", "amount": 45}}

    monkeypatch.setattr(gw, "call_tool", fake_call)
    assert gw.get_order(1003, "C003") == {"order_id": "1003", "customer_id": "C003", "amount": 45}
    assert sent["name"] == "orders___get_order"
    assert sent["arguments"] == {"order_id": "1003", "customer_id": "C003"}   # luôn gửi chuỗi (schema)


def test_not_found_and_other_customer_both_none(gw, monkeypatch):
    monkeypatch.setattr(gw, "call_tool", lambda url, name, arguments: {"found": False})
    assert gw.get_order("1003", "C020") is None


def test_gateway_failure_is_not_swallowed(gw, monkeypatch):
    def broken(url, name, arguments):
        raise GatewayError("http_403")
    monkeypatch.setattr(gw, "call_tool", broken)
    with pytest.raises(GatewayError):          # KHÔNG được biến thành None ("không có đơn")
        gw.get_order("1003", "C003")


def test_pick_backend(gw):
    from tools import get_order as direct
    assert nodes._pick_get_order("direct") is direct.get_order
    assert nodes._pick_get_order("gateway") is gw.get_order
    with pytest.raises(ValueError):
        nodes._pick_get_order("dynamo")        # gõ sai → lỗi ngay, không lặng lẽ chạy đường mặc định
