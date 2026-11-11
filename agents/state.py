"""SupportState: dữ liệu chảy qua graph — "hợp đồng" giữa các node.

Nguyên tắc: mỗi key chỉ một node ghi (node song song không đụng nhau), riêng `steps` nhiều node
cùng cộng nên dùng reducer. Chỉ chứa dữ liệu JSON được (checkpointer sẽ lưu State).
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class SupportState(TypedDict, total=False):
    # Đầu vào — hệ thống đặt lúc invoke, KHÔNG lấy từ câu hỏi
    question: str             # người dùng gõ → không tin được
    customer_id: str          # từ danh tính đã xác thực → tin được
    as_of_date: str           # "hôm nay" theo cấu hình (quy ước AS_OF_DATE), dạng YYYY-MM-DD

    # supervisor ghi
    order_id: str | None      # regex lấy từ câu hỏi; None = câu hỏi không có mã đơn
    route: list[str]          # tập con của ["policy", "order"]; [] = ngoài phạm vi

    # specialist ghi (Day 8) — mỗi node một key
    policy_hits: list[dict]   # policy_node: kết quả search_policy
    order_data: dict | None   # order_node: kết quả get_order

    # writer ghi (Day 8)
    answer: str
    sources: list[str]

    # mọi node cộng dồn: node trả {"steps": 1} → reducer cộng, không ghi đè
    steps: Annotated[int, operator.add]
