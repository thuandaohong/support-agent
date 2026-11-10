"""Tool get_order: tra chính xác 1 đơn hàng theo order_id trong DynamoDB.

Đơn hàng là bản ghi có cấu trúc → tra đúng khóa (get_item), không semantic search như chính sách.
customer_id là bắt buộc và phải lấy từ danh tính đã xác thực (không phải từ câu hỏi): đơn của
người khác trả None y như đơn không tồn tại, để không lộ "mã đơn này có thật".

Chạy thử: python tools/get_order.py 1003 C003
"""
from __future__ import annotations

import json
import os
import sys
from decimal import Decimal

import boto3
from dotenv import load_dotenv

load_dotenv()
REGION = os.environ.get("AWS_REGION", "us-east-1")
ORDERS_TABLE = os.environ["ORDERS_TABLE"]  # thiếu thì lỗi ngay (fail fast)

_table = boto3.resource("dynamodb", region_name=REGION).Table(ORDERS_TABLE)


def get_order(order_id: str, customer_id: str) -> dict | None:
    """Trả đơn dạng dict (cùng cột với orders.csv), hoặc None nếu không có / không phải của khách."""
    resp = _table.get_item(Key={"order_id": str(order_id).strip().lstrip("#")})
    item = resp.get("Item")  # không tìm thấy thì DynamoDB không báo lỗi, chỉ thiếu "Item"
    if item is None or item.get("customer_id") != customer_id:
        return None
    # DynamoDB trả số dạng Decimal → đổi về int để json/LLM dùng thẳng
    return {k: int(v) if isinstance(v, Decimal) else v for k, v in item.items()}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("Cách dùng: python tools/get_order.py <order_id> <customer_id>")
    order = get_order(sys.argv[1], sys.argv[2])
    if order is None:
        sys.exit(f"Không tìm thấy đơn #{sys.argv[1]} của khách {sys.argv[2]}")
    print(json.dumps(order, ensure_ascii=False, indent=2))
