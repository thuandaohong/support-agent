"""Lambda get_order — tool MCP đứng sau AgentCore Gateway (Day 60).

Cùng luật với tools/get_order.py (đường import trực tiếp, giữ làm rollback):
- tra đúng khóa order_id (get_item);
- customer_id BẮT BUỘC, là danh tính đã xác thực do code agent điền (State), không phải do model;
- đơn của người khác trả y như đơn không tồn tại ({"found": false}) → không lộ "mã đơn có thật".

Gateway gọi Lambda theo kiểu tách đôi:
- event   = arguments của tools/call, keyed theo inputSchema ({"order_id": ..., "customer_id": ...})
- context.client_context.custom["bedrockAgentCoreToolName"] = "<target>___<tool>" — Gateway KHÔNG
  tự cắt tiền tố target, phải cắt ở đây.

Không log nội dung đơn hay câu hỏi: chỉ tên tool + kết quả (found / not_found / lỗi).
"""
from __future__ import annotations

import logging
import os
import re
from decimal import Decimal

import boto3

log = logging.getLogger()
log.setLevel(logging.INFO)

DELIM = "___"
REQUIRED = ("order_id", "customer_id")       # khớp "required" trong infra/gateway/get_order.tool.json
_ORDER_ID = re.compile(r"^\d{3,6}$")          # cùng độ dài supervisor bắt được
_CUSTOMER_ID = re.compile(r"^C\d{3,6}$")      # cùng định dạng serve.py kiểm

_table = boto3.resource("dynamodb").Table(os.environ["ORDERS_TABLE"])  # thiếu thì lỗi ngay lúc init


def tool_name(context) -> str | None:
    """Tên tool đã cắt tiền tố target, hoặc None nếu không được gọi qua Gateway."""
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    full = custom.get("bedrockAgentCoreToolName")
    if not full:
        return None
    return full.split(DELIM, 1)[1] if DELIM in full else full


def get_order(order_id: str, customer_id: str) -> dict:
    item = _table.get_item(Key={"order_id": order_id}).get("Item")
    if item is None or item.get("customer_id") != customer_id:
        return {"found": False}
    # DynamoDB trả số dạng Decimal → int, để Gateway serialize JSON được
    return {"found": True, "order": {k: int(v) if isinstance(v, Decimal) else v for k, v in item.items()}}


def lambda_handler(event, context):
    tool = tool_name(context)
    if tool != "get_order":
        log.warning("unknown tool=%s", tool)
        return {"error": "unknown_tool"}

    if not isinstance(event, dict) or any(k not in event for k in REQUIRED):
        log.warning("tool=get_order invalid_input (thiếu trường)")
        return {"error": "invalid_input"}
    order_id = str(event["order_id"]).strip().lstrip("#")
    customer_id = str(event["customer_id"]).strip()
    if not _ORDER_ID.match(order_id) or not _CUSTOMER_ID.match(customer_id):
        log.warning("tool=get_order invalid_input (sai định dạng)")
        return {"error": "invalid_input"}

    result = get_order(order_id, customer_id)
    log.info("tool=get_order result=%s", "found" if result["found"] else "not_found")
    return result
