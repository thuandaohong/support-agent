"""Gọi LLM qua Bedrock Converse API — một chỗ chung cho retry, timeout, đếm token.

Converse dùng chung cho mọi model (Nova, Claude, Llama...) → đổi model chỉ cần đổi model_id.
"""
import os

import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()
REGION = os.environ.get("AWS_REGION", "us-east-1")

_client = boto3.client(
    "bedrock-runtime",
    region_name=REGION,
    # throttle/lỗi mạng: tự thử lại; treo quá 30s thì bỏ thay vì chờ mãi
    config=Config(retries={"max_attempts": 3, "mode": "adaptive"}, read_timeout=30),
)


def converse_text(model_id: str, system: str, user: str,
                  max_tokens: int = 512, temperature: float = 0.0) -> tuple:
    """Gửi 1 lượt chat, trả (text, usage) — usage = {"inputTokens", "outputTokens", ...}."""
    resp = _client.converse(
        modelId=model_id,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    return resp["output"]["message"]["content"][0]["text"], resp.get("usage", {})
