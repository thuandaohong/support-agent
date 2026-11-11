"""Luật nghiệp vụ tính bằng CODE: đơn này còn đổi trả / bảo hành được không.

Vì sao không để LLM tự quyết (Day 55, đo thật): cùng prompt, cùng dữ liệu, Nova Lite lần 1 trả lời
đúng cả 12 câu, lần 2 thì đơn #1026 "shipped" bị hiểu là đã giao và 8 ngày > 7 vẫn bảo "được đổi
trả". Quyết định dính tới tiền và lời hứa với khách phải ra cùng một kết quả mọi lần → code quyết,
LLM chỉ diễn đạt kết luận.

Cái giá: con số thời hạn có ở 2 nơi (bảng dưới đây + file chính sách trong Knowledge Base).
Chống lệch: tests/test_rules.py đọc file chính sách .md và so với bảng này → sửa một bên mà quên
bên kia thì CI báo đỏ.
"""
from __future__ import annotations

import calendar
from datetime import date

# Khớp sample-data/policies/01-return-policy.md, 02-warranty.md (test kiểm tra)
RETURN_DAYS = {"Basic": 7, "Premium": 14, "Pro": 30}
WARRANTY_MONTHS = {"Basic": 6, "Premium": 12, "Pro": 24}

# Theo 06-order-status.md: chỉ đơn đã giao mới đổi trả / bảo hành được
NOT_DELIVERED_YET = {"processing", "shipped"}   # chờ giao xong (thời hạn vẫn chạy từ ngày đặt)


def add_months(d: date, months: int) -> date:
    """Cộng tháng, ngày vượt cuối tháng thì lấy ngày cuối (31/08 + 6 tháng → 28 hoặc 29/02)."""
    month_index = d.month - 1 + months
    year, month = d.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _status_block(status: str, refunded_reason: str) -> str | None:
    """Lý do trạng thái đơn chặn quyền lợi, hoặc None nếu đơn đã giao (xét tiếp thời hạn)."""
    if status in NOT_DELIVERED_YET:
        return "not_delivered_yet"
    if status == "cancelled":
        return "cancelled"
    if status == "refunded":
        return refunded_reason
    return None


def check_return(order: dict, as_of: str) -> dict:
    """Kết luận đổi trả cho 1 đơn tại ngày as_of (YYYY-MM-DD).

    Trả về dict đưa thẳng cho writer, ví dụ:
      {"eligible": True, "reason": "within_period", "period_days": 14,
       "days_since_order": 6, "last_day": "2026-11-16"}
    reason ∈ within_period | expired | not_delivered_yet | cancelled | already_refunded
    """
    ordered = date.fromisoformat(order["order_date"])
    period = RETURN_DAYS[order["plan"]]
    days = (date.fromisoformat(as_of) - ordered).days    # "số ngày = ngày yêu cầu − ngày đặt"
    result = {"period_days": period, "days_since_order": days,
              "last_day": date.fromordinal(ordered.toordinal() + period).isoformat()}

    blocked = _status_block(order["status"], "already_refunded")
    if blocked:
        return {"eligible": False, "reason": blocked, **result}
    # "nhỏ hơn hoặc bằng thời hạn (tính cả ngày cuối cùng)" → dùng <=, không phải <
    if days <= period:
        return {"eligible": True, "reason": "within_period", **result}
    return {"eligible": False, "reason": "expired", **result}


def check_warranty(order: dict, as_of: str) -> dict:
    """Kết luận bảo hành: còn hạn nếu as_of <= ngày đặt + N tháng (theo gói), và đơn đã giao.

    reason ∈ within_period | expired | not_delivered_yet | cancelled | refunded
    """
    ordered = date.fromisoformat(order["order_date"])
    months = WARRANTY_MONTHS[order["plan"]]
    until = add_months(ordered, months)
    result = {"period_months": months, "warranty_until": until.isoformat()}

    blocked = _status_block(order["status"], "refunded")
    if blocked:
        return {"eligible": False, "reason": blocked, **result}
    if date.fromisoformat(as_of) <= until:
        return {"eligible": True, "reason": "within_period", **result}
    return {"eligible": False, "reason": "expired", **result}
