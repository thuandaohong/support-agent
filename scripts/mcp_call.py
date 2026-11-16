"""Gọi tool trên AgentCore Gateway qua MCP (Day 60 bước 4) — kiểm Gateway → Lambda → DynamoDB.

Chạy:  python scripts/mcp_call.py                 (tools/list + 3 ca chuẩn, tự kiểm)
       python scripts/mcp_call.py list
       python scripts/mcp_call.py call 1003 C003

Ký SigV4 bằng credentials đang dùng (máy dev: user của mình; cần bedrock-agentcore:InvokeGateway).
URL Gateway tra theo tên (GATEWAY_NAME) — không lưu URL/account ID vào code.
"""
import json
import os
import sys
import time
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.mcp_client import GatewayError, call_tool, list_tools

REGION = os.environ.get("AWS_REGION", "us-east-1")
GATEWAY_NAME = os.environ.get("GATEWAY_NAME", "support-gateway")
TOOL = f"{os.environ.get('TARGET_NAME', 'orders')}___get_order"

CASES = [  # (order_id, customer_id, found mong đợi)
    ("1003", "C003", True),    # đơn của chính khách
    ("1003", "C020", False),   # đơn của người khác → giống hệt không tồn tại
    ("9999", "C003", False),   # không tồn tại
]


def gateway_url() -> str:
    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    for gw in control.list_gateways()["items"]:
        if gw["name"] == GATEWAY_NAME:
            return control.get_gateway(gatewayIdentifier=gw["gatewayId"])["gatewayUrl"]
    sys.exit(f"Không thấy Gateway {GATEWAY_NAME} ở {REGION}")


def timed_call(url: str, order_id: str, customer_id: str) -> tuple[dict, float]:
    t0 = time.perf_counter()
    out = call_tool(url, TOOL, {"order_id": order_id, "customer_id": customer_id})
    return out, (time.perf_counter() - t0) * 1000


def main():
    url = gateway_url()
    args = sys.argv[1:]
    if args[:1] == ["list"]:
        print(json.dumps(list_tools(url), ensure_ascii=False, indent=2))
    elif args[:1] == ["call"] and len(args) == 3:
        out, ms = timed_call(url, args[1], args[2])
        print(json.dumps(out, ensure_ascii=False, indent=2), f"\n({ms:.0f} ms)")
    elif not args:
        names = [t["name"] for t in list_tools(url)]
        print(f"tools/list: {names}  {'✅' if TOOL in names else '❌ thiếu ' + TOOL}")
        passed = TOOL in names
        for order_id, customer_id, want in CASES:
            out, ms = timed_call(url, order_id, customer_id)
            ok = out.get("found") is want
            passed &= ok
            print(f"tools/call {order_id}/{customer_id} → found={out.get('found')}  ({ms:.0f} ms) {'✅' if ok else '❌'}")
        try:
            call_tool(url, TOOL, {"order_id": "1003"})     # thiếu customer_id
            print("thiếu customer_id → KHÔNG bị chặn ❌")
            passed = False
        except GatewayError as e:
            print(f"thiếu customer_id → bị chặn ({e}) ✅")
        print("Gateway OK" if passed else "Gateway CÓ LỖI")
        sys.exit(0 if passed else 1)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
