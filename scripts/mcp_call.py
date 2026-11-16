"""Gọi tool trên AgentCore Gateway qua MCP (Day 60–61) — kiểm Gateway → Lambda → DynamoDB / KB.

Chạy:  python scripts/mcp_call.py                 (tools/list + các ca chuẩn của 2 tool, tự kiểm)
       python scripts/mcp_call.py list
       python scripts/mcp_call.py call 1003 C003
       python scripts/mcp_call.py policy "Gói Premium đổi trả mấy ngày?"

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
POLICY_TOOL = f"{os.environ.get('POLICY_TARGET_NAME', 'policies')}___search_policy"

CASES = [  # (order_id, customer_id, found mong đợi)
    ("1003", "C003", True),    # đơn của chính khách
    ("1003", "C020", False),   # đơn của người khác → giống hệt không tồn tại
    ("9999", "C003", False),   # không tồn tại
]


POLICY_CASES = [  # (câu hỏi, file phải có trong kết quả — None: chỉ cần không lỗi)
    ("Gói Premium được đổi trả trong bao nhiêu ngày?", "01-return-policy.md"),
    ("How long is the warranty for the Pro plan?", "02-warranty.md"),
    ("Thủ đô của Pháp là gì?", None),           # lạc đề: vẫn trả đoạn (điểm thấp), không phải lỗi
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


def timed_policy(url: str, query: str) -> tuple[list[dict], float]:
    t0 = time.perf_counter()
    hits = call_tool(url, POLICY_TOOL, {"query": query})["hits"]
    return hits, (time.perf_counter() - t0) * 1000


def files(hits: list[dict]) -> list[str]:
    return [h["source"].rsplit("/", 1)[-1] for h in hits]


def main():
    url = gateway_url()
    args = sys.argv[1:]
    if args[:1] == ["list"]:
        print(json.dumps(list_tools(url), ensure_ascii=False, indent=2))
    elif args[:1] == ["call"] and len(args) == 3:
        out, ms = timed_call(url, args[1], args[2])
        print(json.dumps(out, ensure_ascii=False, indent=2), f"\n({ms:.0f} ms)")
    elif args[:1] == ["policy"] and len(args) == 2:
        hits, ms = timed_policy(url, args[1])
        for h in hits:   # in tên file + điểm + đoạn đầu (câu hỏi là của mình gõ, không phải của khách)
            print(f"{h['score']:.2f}  {files([h])[0]}  {h['text'][:80]!r}")
        print(f"({ms:.0f} ms)")
    elif not args:
        names = [t["name"] for t in list_tools(url)]
        missing = [t for t in (TOOL, POLICY_TOOL) if t not in names]
        print(f"tools/list: {names}  {'✅' if not missing else '❌ thiếu ' + ', '.join(missing)}")
        passed = not missing
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
        for query, want in POLICY_CASES:
            hits, ms = timed_policy(url, query)
            ok = bool(hits) and (want is None or want in files(hits))
            passed &= ok
            print(f"search_policy {query[:40]!r} → {files(hits)}  ({ms:.0f} ms) {'✅' if ok else '❌'}")
        for bad in ({"query": "x" * 2001}, {"query": "đổi trả", "top_k": 9}, {"query": "đổi trả", "top_k": "3"}):
            label = {k: (v if len(str(v)) < 10 else f"<{len(v)} ký tự>") for k, v in bad.items()}
            try:
                call_tool(url, POLICY_TOOL, bad)
                print(f"search_policy {label} → KHÔNG bị chặn ❌")
                passed = False
            except GatewayError as e:
                print(f"search_policy {label} → bị chặn ({e}) ✅")
        print("Gateway OK" if passed else "Gateway CÓ LỖI")
        sys.exit(0 if passed else 1)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
