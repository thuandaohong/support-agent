"""Tool search_policy: tra Knowledge Base chính sách, trả các đoạn liên quan + nguồn.

Tool chỉ lấy "nguyên liệu" (list dict có cấu trúc), không viết câu trả lời — việc đó của
Writer node. Sau này policy_node trong LangGraph sẽ gọi hàm này.

Chạy thử: python tools/search_policy.py "Gói Premium đổi trả bao nhiêu ngày?"
"""
import json
import os
import sys

import boto3
from dotenv import load_dotenv

load_dotenv()
REGION = os.environ.get("AWS_REGION", "us-east-1")
POLICY_KB_ID = os.environ["POLICY_KB_ID"]  # thiếu thì lỗi ngay (fail fast)

_client = boto3.client("bedrock-agent-runtime", region_name=REGION)


def search_policy(query: str, top_k: int = 3) -> list:
    """Trả tối đa top_k đoạn: [{"text", "source", "score"}], điểm cao nhất trước."""
    # KB loại MANAGED không nhận vectorSearchConfiguration (numberOfResults) → lấy mặc
    # định (5 đoạn) rồi tự cắt, giống handler.retrieve() ở Project #1
    resp = _client.retrieve(
        knowledgeBaseId=POLICY_KB_ID,
        retrievalQuery={"text": query},
    )
    results = []
    for item in resp.get("retrievalResults", [])[:top_k]:
        results.append({
            "text": item["content"]["text"],
            "source": item["location"]["s3Location"]["uri"],
            "score": item.get("score"),
        })
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('Cách dùng: python tools/search_policy.py "câu hỏi"')
    print(json.dumps(search_policy(sys.argv[1]), ensure_ascii=False, indent=2))
