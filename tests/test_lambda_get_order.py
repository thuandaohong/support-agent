"""Test Lambda get_order (Day 60) — bảng DynamoDB thay bằng dict giả, context giả như Gateway gửi.

Không gọi AWS, chạy trên CI. Quan trọng nhất: đơn của người khác phải trả GIỐNG HỆT đơn không tồn tại.
"""
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from lambdas.get_order import handler

SCHEMA = Path(__file__).resolve().parent.parent / "infra" / "gateway" / "get_order.tool.json"

ORDERS = {
    "1003": {"order_id": "1003", "customer_id": "C003", "plan": "Premium", "status": "delivered",
             "order_date": "2026-11-02", "amount": Decimal(45)},
}


class FakeTable:
    def __init__(self):
        self.keys = []

    def get_item(self, Key):
        self.keys.append(Key)
        item = ORDERS.get(Key["order_id"])
        return {"Item": dict(item)} if item else {}   # không có thì DynamoDB chỉ thiếu "Item"


@pytest.fixture
def table(monkeypatch):
    t = FakeTable()
    monkeypatch.setattr(handler, "_table", t)
    return t


def ctx(tool="orders___get_order"):
    custom = {"bedrockAgentCoreToolName": tool} if tool else {}
    return SimpleNamespace(client_context=SimpleNamespace(custom=custom))


def test_found_strips_target_prefix_and_converts_decimal(table):
    out = handler.lambda_handler({"order_id": "1003", "customer_id": "C003"}, ctx())
    assert out["found"] is True
    assert out["order"]["plan"] == "Premium"
    assert out["order"]["amount"] == 45 and isinstance(out["order"]["amount"], int)
    json.dumps(out)                                   # Gateway phải serialize được


def test_other_customers_order_looks_exactly_like_missing(table):
    other = handler.lambda_handler({"order_id": "1003", "customer_id": "C020"}, ctx())
    missing = handler.lambda_handler({"order_id": "9999", "customer_id": "C003"}, ctx())
    assert other == missing == {"found": False}


@pytest.mark.parametrize("event, key", [
    ({"order_id": "#1003", "customer_id": "C003"}, "1003"),     # có dấu # như câu khách gõ
    ({"order_id": 1003, "customer_id": " C003 "}, "1003"),      # client gửi số / có khoảng trắng
])
def test_normalizes_input(table, event, key):
    assert handler.lambda_handler(event, ctx())["found"] is True
    assert table.keys == [{"order_id": key}]


@pytest.mark.parametrize("event", [
    {"order_id": "1003"},                                        # thiếu customer_id
    {"customer_id": "C003"},                                     # thiếu order_id
    {"order_id": "1003", "customer_id": "admin"},                # sai định dạng khách
    {"order_id": "10; DROP", "customer_id": "C003"},             # sai định dạng đơn
    {"order_id": "12", "customer_id": "C003"},                   # quá ngắn
    "không phải dict",
])
def test_invalid_input_never_reaches_dynamodb(table, event):
    assert handler.lambda_handler(event, ctx()) == {"error": "invalid_input"}
    assert table.keys == []


@pytest.mark.parametrize("tool", ["orders___delete_order", "get_orders", None])
def test_unknown_tool_or_not_via_gateway(table, tool):
    assert handler.lambda_handler({"order_id": "1003", "customer_id": "C003"}, ctx(tool)) == {"error": "unknown_tool"}
    assert table.keys == []


def test_tool_name_without_prefix_still_works(table):
    assert handler.tool_name(ctx("get_order")) == "get_order"
    assert handler.tool_name(SimpleNamespace(client_context=None)) is None


def test_schema_matches_handler_contract():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["name"] == "get_order"
    assert tuple(schema["inputSchema"]["required"]) == handler.REQUIRED
    assert set(schema["inputSchema"]["properties"]) == set(handler.REQUIRED)
