"""Test hàm thuần của supervisor — không gọi AWS, chạy được trong CI."""
import pytest

from agents.supervisor import extract_order_id, parse_route


@pytest.mark.parametrize("question, expected", [
    ("Đơn #1003 giao tới đâu rồi?", "1003"),
    ("đơn 1003 còn đổi trả được không", "1003"),
    ("Đơn hàng số 1019 của tôi", "1019"),
    ("Can I return order #1019?", "1019"),
    ("order no. 1050 status", "1050"),
    ("mã đơn # 9999", "9999"),
    ("Tôi đặt hàng năm 2026, gói Pro 30 ngày", None),   # số khác không phải mã đơn
    ("Đơn của tôi bao giờ tới?", None),
    ("Gói Premium đổi trả mấy ngày?", None),
])
def test_extract_order_id(question, expected):
    assert extract_order_id(question) == expected


@pytest.mark.parametrize("text, expected", [
    ('{"route": ["policy"]}', ["policy"]),
    ('{"route": ["order", "policy"]}', ["policy", "order"]),         # chuẩn hoá thứ tự
    ('Here is the result: {"route": ["order"]} done', ["order"]),     # chữ quanh JSON
    ('{"route": ["policy", "billing", "policy"]}', ["policy"]),       # lọc rác + trùng
    ('{"route": []}', []),                                            # ngoài phạm vi
    ("I cannot help with that", None),                                # không có JSON
    ('{"route": "policy"}', None),                                    # sai kiểu
    ('{"route": [}', None),                                           # JSON hỏng
    ('["policy"]', None),                                             # không phải object
])
def test_parse_route(text, expected):
    assert parse_route(text) == expected
