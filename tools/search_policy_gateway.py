"""Tool search_policy qua AgentCore Gateway (Day 61) — CÙNG hợp đồng với tools/search_policy.search_policy.

policy_node không cần biết chính sách được tra bằng đường nào: cả hai trả list đoạn
[{"text", "source", "score"}] (có thể rỗng = không có đoạn liên quan). Khác biệt duy nhất: đường
Gateway có thể hỏng giữa chừng → ném GatewayError để policy_node báo "đang bận", KHÔNG được coi là
"không có chính sách" (list rỗng).

Đường đi: mcp_client (HTTPS + SigV4 bằng role đang chạy) → Gateway → Lambda support-search-policy →
Bedrock Knowledge Base.

Chỉ được import khi POLICY_BACKEND=gateway (agents/nodes.py) → thiếu GATEWAY_URL thì lỗi ngay lúc
khởi động (fail fast).

Chạy thử: GATEWAY_URL=https://…/mcp python tools/search_policy_gateway.py "Gói Premium đổi trả mấy ngày?"
"""
from __future__ import annotations

import json
import os
import sys

from tools.mcp_client import GatewayError, call_tool

GATEWAY_URL = os.environ["GATEWAY_URL"]
# Tên tool Gateway công bố = "<tên target>___<tên trong tool schema>" (infra/gateway/07-policy-target.sh)
TOOL = f"{os.environ.get('GATEWAY_POLICY_TARGET', 'policies')}___search_policy"


def search_policy(query: str, top_k: int = 3) -> list:
    """Trả tối đa top_k đoạn, điểm cao nhất trước. Gateway hỏng / trả sai định dạng → GatewayError."""
    data = call_tool(GATEWAY_URL, TOOL, {"query": query, "top_k": top_k})
    hits = data.get("hits") if isinstance(data, dict) else None
    if not isinstance(hits, list):
        raise GatewayError("tool_bad_output")
    return hits


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('Cách dùng: python tools/search_policy_gateway.py "câu hỏi"')
    print(json.dumps(search_policy(sys.argv[1]), ensure_ascii=False, indent=2))
