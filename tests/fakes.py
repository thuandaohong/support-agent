"""Dữ liệu giả dùng chung cho test không gọi AWS (fixture fake_aws ở conftest.py)."""

ORDERS = {  # "DynamoDB" giả: order_id → đơn
    "1003": {"order_id": "1003", "customer_id": "C003", "plan": "Premium",
             "status": "delivered", "order_date": "2026-11-02", "amount": 45},
}
HITS = [
    {"text": "Premium: 14 ngày", "source": "https://b.s3.amazonaws.com/policies/01-return-policy.md", "score": 0.5},
    {"text": "ví dụ", "source": "https://b.s3.amazonaws.com/policies/01-return-policy.md", "score": 0.4},
    {"text": "gói", "source": "https://b.s3.amazonaws.com/policies/03-service-plans.md", "score": 0.3},
]
