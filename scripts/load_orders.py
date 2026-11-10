"""Nạp sample-data/orders.csv vào bảng DynamoDB (chạy lại được: put_item ghi đè theo order_id).

Chạy: python scripts/load_orders.py
"""
import csv
import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv()
REGION = os.environ.get("AWS_REGION", "us-east-1")
ORDERS_TABLE = os.environ["ORDERS_TABLE"]
CSV_PATH = Path(__file__).resolve().parent.parent / "sample-data" / "orders.csv"


def main():
    table = boto3.resource("dynamodb", region_name=REGION).Table(ORDERS_TABLE)
    with open(CSV_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # batch_writer gom put thành lô 25 item, tự retry phần bị throttle
    with table.batch_writer() as batch:
        for row in rows:
            row["amount"] = int(row["amount"])  # Number trong DynamoDB; order_id giữ String
            batch.put_item(Item=row)
    print(f"Đã nạp {len(rows)} đơn vào bảng {ORDERS_TABLE}")


if __name__ == "__main__":
    main()
