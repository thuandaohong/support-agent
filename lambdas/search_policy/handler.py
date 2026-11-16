"""Lambda search_policy — tool MCP đứng sau AgentCore Gateway (Day 61).

Cùng kết quả với tools/search_policy.py (đường import trực tiếp, giữ làm rollback): tra Knowledge Base
chính sách, trả tối đa top_k đoạn [{"text", "source", "score"}], điểm cao nhất trước.

Gateway gọi Lambda theo kiểu tách đôi (giống get_order):
- event   = arguments của tools/call ({"query": ..., "top_k": ...})
- context.client_context.custom["bedrockAgentCoreToolName"] = "<target>___search_policy" → tự cắt tiền tố.

Gateway CHỈ kiểm "required" + kiểu trong inputSchema (schema của Gateway không nhận maxLength /
minimum / maximum) → độ dài query và khoảng top_k phải kiểm ở đây.

query là CÂU HỎI CỦA KHÁCH (văn bản tự do, có thể có thông tin cá nhân) → KHÔNG log nội dung,
chỉ log độ dài + số đoạn trả về (quy định từ Project #1).
"""
from __future__ import annotations

import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError

log = logging.getLogger()
log.setLevel(logging.INFO)

DELIM = "___"
REQUIRED = ("query",)        # khớp "required" trong infra/gateway/search_policy.tool.json
MAX_QUERY = 2000             # cùng giới hạn serve.py đặt cho câu hỏi
MAX_TOP_K = 5                # KB MANAGED trả mặc định 5 đoạn → không xin hơn được
DEFAULT_TOP_K = 3

POLICY_KB_ID = os.environ["POLICY_KB_ID"]           # thiếu thì lỗi ngay lúc init
_client = boto3.client("bedrock-agent-runtime")


def tool_name(context) -> str | None:
    """Tên tool đã cắt tiền tố target, hoặc None nếu không được gọi qua Gateway."""
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    full = custom.get("bedrockAgentCoreToolName")
    if not full:
        return None
    return full.split(DELIM, 1)[1] if DELIM in full else full


def search_policy(query: str, top_k: int) -> list[dict]:
    # KB loại MANAGED không nhận vectorSearchConfiguration (numberOfResults) → lấy mặc định rồi tự cắt
    resp = _client.retrieve(knowledgeBaseId=POLICY_KB_ID, retrievalQuery={"text": query})
    return [{"text": r["content"]["text"],
             "source": r["location"]["s3Location"]["uri"],
             "score": r.get("score")}
            for r in resp.get("retrievalResults", [])[:top_k]]


def parse_top_k(value) -> int | None:
    """top_k hợp lệ (1..MAX_TOP_K), mặc định khi vắng; sai → None. bool là int trong Python → loại riêng."""
    if value is None:
        return DEFAULT_TOP_K
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_TOP_K:
        return None
    return value


def lambda_handler(event, context):
    tool = tool_name(context)
    if tool != "search_policy":
        log.warning("unknown tool=%s", tool)
        return {"error": "unknown_tool"}

    if not isinstance(event, dict) or not isinstance(event.get("query"), str):
        log.warning("tool=search_policy invalid_input (thiếu query)")
        return {"error": "invalid_input"}
    query = event["query"].strip()
    top_k = parse_top_k(event.get("top_k"))
    if not query or len(query) > MAX_QUERY or top_k is None:
        log.warning("tool=search_policy invalid_input query_len=%d", len(query))
        return {"error": "invalid_input"}

    try:
        hits = search_policy(query, top_k)
    except (ClientError, BotoCoreError) as e:
        # Mã lỗi AWS (ThrottlingException, ResourceNotFoundException…) đủ để debug, không lộ câu hỏi
        code = e.response["Error"]["Code"] if isinstance(e, ClientError) else type(e).__name__
        log.error("tool=search_policy kb_error=%s", code)
        return {"error": "kb_unavailable"}

    log.info("tool=search_policy query_len=%d top_k=%d hits=%d", len(query), top_k, len(hits))
    return {"hits": hits}
