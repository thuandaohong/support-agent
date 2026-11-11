"""Test luật đổi trả / bảo hành (agents/rules.py) — các trường hợp biên của bộ dữ liệu.

Kèm test CHỐNG LỆCH: đọc file chính sách .md (cũng là thứ nạp vào Knowledge Base) và so với bảng
RETURN_DAYS / WARRANTY_MONTHS trong code. Sửa chính sách mà quên sửa code (hoặc ngược lại) → đỏ.
"""
import re
from datetime import date
from pathlib import Path

import pytest

from agents.rules import (
    RETURN_DAYS,
    WARRANTY_MONTHS,
    add_months,
    check_return,
    check_warranty,
)

POLICIES = Path(__file__).resolve().parent.parent / "sample-data" / "policies"
AS_OF = "2026-11-08"


def order(plan, status, order_date):
    return {"plan": plan, "status": status, "order_date": order_date}


# ─── đổi trả: các đơn biên có thật trong orders.csv ───

@pytest.mark.parametrize("o, eligible, reason, days", [
    (order("Premium", "delivered", "2026-11-02"), True, "within_period", 6),      # #1003
    (order("Pro", "delivered", "2026-10-09"), True, "within_period", 30),         # #1019 đúng ngày cuối
    (order("Premium", "delivered", "2026-10-25"), True, "within_period", 14),     # #1014 đúng ngày cuối
    (order("Basic", "delivered", "2026-11-01"), True, "within_period", 7),        # #1050 đúng ngày cuối
    (order("Premium", "delivered", "2026-10-24"), False, "expired", 15),          # #1008 quá 1 ngày
    (order("Basic", "shipped", "2026-10-31"), False, "not_delivered_yet", 8),     # #1026
    (order("Pro", "processing", "2026-10-04"), False, "not_delivered_yet", 35),   # #1002
    (order("Pro", "cancelled", "2026-10-11"), False, "cancelled", 28),            # #1036
    (order("Basic", "refunded", "2026-10-17"), False, "already_refunded", 22),    # #1007
])
def test_check_return(o, eligible, reason, days):
    r = check_return(o, AS_OF)
    assert (r["eligible"], r["reason"], r["days_since_order"]) == (eligible, reason, days)


def test_return_last_day():
    # Premium đặt 2026-11-02 → ngày cuối còn đổi trả = 2026-11-16 (14 ngày sau)
    assert check_return(order("Premium", "delivered", "2026-11-02"), AS_OF)["last_day"] == "2026-11-16"


# ─── bảo hành ───

@pytest.mark.parametrize("o, as_of, eligible, reason, until", [
    (order("Basic", "delivered", "2026-05-08"), "2026-11-08", True, "within_period", "2026-11-08"),  # đúng ngày cuối
    (order("Basic", "delivered", "2026-05-07"), "2026-11-08", False, "expired", "2026-11-07"),
    (order("Premium", "delivered", "2026-11-02"), AS_OF, True, "within_period", "2027-11-02"),
    (order("Pro", "shipped", "2026-10-31"), AS_OF, False, "not_delivered_yet", "2028-10-31"),
    (order("Basic", "refunded", "2026-10-17"), AS_OF, False, "refunded", "2027-04-17"),
])
def test_check_warranty(o, as_of, eligible, reason, until):
    r = check_warranty(o, as_of)
    assert (r["eligible"], r["reason"], r["warranty_until"]) == (eligible, reason, until)


@pytest.mark.parametrize("start, months, expected", [
    (date(2026, 8, 31), 6, date(2027, 2, 28)),    # tháng 2 không có ngày 31 → ngày cuối tháng
    (date(2027, 8, 31), 6, date(2028, 2, 29)),    # năm nhuận
    (date(2026, 11, 2), 12, date(2027, 11, 2)),
    (date(2026, 10, 15), 3, date(2027, 1, 15)),   # qua năm
])
def test_add_months(start, months, expected):
    assert add_months(start, months) == expected


# ─── chống lệch giữa code và file chính sách ───

def test_return_days_match_policy_doc():
    text = (POLICIES / "01-return-policy.md").read_text(encoding="utf-8")
    # dòng dạng: - **Gói Premium**: đổi trả trong vòng **14 ngày**.
    found = {plan: int(n) for plan, n in re.findall(r"Gói (\w+)\**: đổi trả trong vòng \**(\d+) ngày", text)}
    assert found == RETURN_DAYS


def test_warranty_months_match_policy_doc():
    text = (POLICIES / "02-warranty.md").read_text(encoding="utf-8")
    # dòng dạng: - Gói Premium: bảo hành **12 tháng**.
    found = {plan: int(n) for plan, n in re.findall(r"Gói (\w+)\**: bảo hành \**(\d+) tháng", text)}
    assert found == WARRANTY_MONTHS
