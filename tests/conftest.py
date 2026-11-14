"""Cấu hình chung cho pytest — chạy TRƯỚC khi file test nào import code.

tools/*.py đọc POLICY_KB_ID / ORDERS_TABLE ngay lúc import (fail fast). Trên CI không có .env nên
đặt giá trị giả ở đây. Tạo boto3 client không cần credentials; test thay hết lời gọi AWS bằng hàm
giả nên không có request thật nào được gửi.

RUN_INTEGRATION=1 (test gọi AWS thật, tests/test_integration.py): nạp .env THẬT trước. Phải làm ở
đây vì load_dotenv() mặc định KHÔNG ghi đè biến đã có — nếu setdefault giá trị giả chạy trước thì
tools/ sẽ gọi vào KB "TEST_KB" không tồn tại.
"""
import os

from dotenv import load_dotenv

if os.environ.get("RUN_INTEGRATION") == "1":
    load_dotenv()

os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("POLICY_KB_ID", "TEST_KB")
os.environ.setdefault("ORDERS_TABLE", "test-orders")
