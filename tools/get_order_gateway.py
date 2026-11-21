"""Tool get_order qua AgentCore Gateway (Day 60) — CÙNG hợp đồng với tools/get_order.get_order.

order_node không cần biết đơn được tra bằng đường nào: cả hai trả dict đơn hàng, hoặc None khi
không có / không phải của khách. Khác biệt duy nhất: đường Gateway có thể hỏng giữa chừng (mạng,
quyền, Lambda lỗi) → ném GatewayError để order_node báo "đang bận", KHÔNG được coi là "không có đơn".

Đường đi: mcp_client (HTTPS + SigV4 bằng role đang chạy) → Gateway → Lambda support-get-order →
DynamoDB. Lambda tự chặn đơn của người khác ({"found": false}, giống hệt đơn không tồn tại).

Chỉ được import khi ORDER_BACKEND=gateway (agents/nodes.py) → thiếu GATEWAY_URL thì lỗi ngay lúc
khởi động (fail fast), không đợi tới câu hỏi đầu tiên.

Chạy thử: ORDER_BACKEND=gateway GATEWAY_URL=https://…/mcp python tools/get_order_gateway.py 1003 C003
"""
from __future__ import annotations

import json
import os
import sys

from tools.mcp_client import call_tool

GATEWAY_URL = os.environ["GATEWAY_URL"]
# Tên tool Gateway công bố = "<tên target>___<tên trong tool schema>" (infra/terraform/modules/gateway)
TOOL = f"{os.environ.get('GATEWAY_TARGET', 'orders')}___get_order"


def get_order(order_id: str, customer_id: str) -> dict | None:
    """Trả đơn dạng dict, None nếu không có / không phải của khách. Gateway hỏng → GatewayError."""
    data = call_tool(GATEWAY_URL, TOOL, {"order_id": str(order_id), "customer_id": customer_id})
    return data["order"] if data.get("found") else None


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("Cách dùng: python tools/get_order_gateway.py <order_id> <customer_id>")
    order = get_order(sys.argv[1], sys.argv[2])
    if order is None:
        sys.exit(f"Không tìm thấy đơn #{sys.argv[1]} của khách {sys.argv[2]}")
    print(json.dumps(order, ensure_ascii=False, indent=2))
