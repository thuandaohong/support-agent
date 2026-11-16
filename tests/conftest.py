"""Cấu hình chung cho pytest — chạy TRƯỚC khi file test nào import code.

tools/*.py đọc POLICY_KB_ID / ORDERS_TABLE ngay lúc import (fail fast). Trên CI không có .env nên
đặt giá trị giả ở đây. Tạo boto3 client không cần credentials; test thay hết lời gọi AWS bằng hàm
giả nên không có request thật nào được gửi.

RUN_INTEGRATION=1 (test gọi AWS thật, tests/test_integration.py): nạp .env THẬT trước. Phải làm ở
đây vì load_dotenv() mặc định KHÔNG ghi đè biến đã có — nếu setdefault giá trị giả chạy trước thì
tools/ sẽ gọi vào KB "TEST_KB" không tồn tại.
"""
import os

from dotenv import load_dotenv

if os.environ.get("RUN_INTEGRATION") == "1":
    load_dotenv()

os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("POLICY_KB_ID", "TEST_KB")
os.environ.setdefault("ORDERS_TABLE", "test-orders")


import pytest


@pytest.fixture
def fake_aws(monkeypatch):
    """Thay mọi lời gọi AWS (LLM, KB, DynamoDB). Trả dict `calls` để test xem node nào đã gọi gì."""
    from fakes import HITS, ORDERS

    from agents import nodes, supervisor

    calls = {"router_reply": '{"route": ["policy", "order"]}', "writer": 0, "search": 0}

    def fake_converse(model_id, system, user, max_tokens=512, temperature=0.0):
        if system is supervisor.ROUTER_PROMPT:          # router
            calls["router_input"] = user
            return calls["router_reply"], {}
        calls["writer"] += 1                            # writer
        calls["writer_input"] = user
        return "câu trả lời giả", {}

    def fake_search(query, top_k=3):
        calls["search"] += 1
        return HITS

    def fake_get_order(order_id, customer_id):
        order = ORDERS.get(order_id)
        # giống tool thật: đơn của người khác → None
        return dict(order) if order and order["customer_id"] == customer_id else None

    monkeypatch.setattr(supervisor, "converse_text", fake_converse)
    monkeypatch.setattr(nodes, "converse_text", fake_converse)
    monkeypatch.setattr(nodes, "search_policy", fake_search)
    monkeypatch.setattr(nodes, "get_order", fake_get_order)
    return calls
