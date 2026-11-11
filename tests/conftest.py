"""Cấu hình chung cho pytest — chạy TRƯỚC khi file test nào import code.

tools/*.py đọc POLICY_KB_ID / ORDERS_TABLE ngay lúc import (fail fast). Trên CI không có .env nên
đặt giá trị giả ở đây. Tạo boto3 client không cần credentials; test thay hết lời gọi AWS bằng hàm
giả nên không có request thật nào được gửi.
"""
import os

os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("POLICY_KB_ID", "TEST_KB")
os.environ.setdefault("ORDERS_TABLE", "test-orders")
