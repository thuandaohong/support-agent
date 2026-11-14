"""Test ĐỈNH kim tự tháp: gọi AWS thật (Knowledge Base, DynamoDB, Bedrock). Mặc định BỎ QUA.

Chạy:  RUN_INTEGRATION=1 python -m pytest -v tests/test_integration.py
Cần:   .env thật + credentials AWS. Tốn ~$0.005 / lần (3 lần gọi Nova Lite + 3 lần retrieve).

Mỗi test kiểm MỘT tầng (KB → DynamoDB → cả graph), để khi đỏ biết ngay hỏng ở đâu.
Chỉ assert phần TẤT ĐỊNH (nguồn, route, order_lookup, steps) — không so nguyên văn câu trả lời
của LLM, vì model diễn đạt mỗi lần một khác → test sẽ chập chờn. Chất lượng câu trả lời để eval
(agents/try_graph.py, Phase E) chấm.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1",
    reason="gọi AWS thật — đặt RUN_INTEGRATION=1 để chạy",
)

AS_OF = "2026-11-08"   # quy ước eval (sample-data/README.md)


# ─── tầng tool ───

def test_search_policy_finds_return_policy():
    from tools.search_policy import search_policy

    hits = search_policy("Gói Premium được đổi trả trong bao nhiêu ngày?", top_k=3)
    assert 1 <= len(hits) <= 3
    assert any(h["source"].endswith("/01-return-policy.md") for h in hits)
    assert all(h["text"] for h in hits)


def test_get_order_found_for_owner():
    from tools.get_order import get_order

    order = get_order("1003", "C003")
    assert order is not None
    assert (order["plan"], order["status"], order["order_date"]) == ("Premium", "delivered", "2026-11-02")
    assert isinstance(order["amount"], int)   # Decimal của DynamoDB đã đổi sang int


def test_get_order_hides_other_customers_order():
    from tools.get_order import get_order

    assert get_order("1036", "C020") is None   # đơn 1036 là của C035
    assert get_order("9999", "C003") is None   # không tồn tại — trông giống hệt ca trên


# ─── tầng graph (qua cửa vào ask) ───

def test_ask_order_and_policy_end_to_end():
    from agents.graph import ask

    out = ask("Đơn #1003 gói Premium của tôi còn đổi trả được không?", "C003", as_of_date=AS_OF)
    assert out["route"] == ["policy", "order"]
    assert out["order_lookup"] == "found"
    assert out["steps"] == 4
    assert "orders/1003" in out["sources"] and "01-return-policy.md" in out["sources"]
    assert out["answer"]


def test_ask_greeting_skips_tools():
    from agents.graph import ask

    out = ask("Xin chào", "C003", as_of_date=AS_OF)
    assert (out["route"], out["steps"], out["sources"]) == ([], 2, [])
    assert out["answer"].startswith("Chào bạn!")
