"""Đọc bộ eval + chấm phần TẤT ĐỊNH — dùng chung cho agents/try_graph.py (local) và
scripts/invoke_runtime.py (qua AgentCore Runtime), để hai nơi chấm cùng một luật.

graph_cases.jsonl        — mỗi dòng 1 câu hỏi độc lập
conversation_cases.jsonl — mỗi dòng 1 hội thoại nhiều lượt cùng session (Day 62)

Giá trị mong đợi trong file:
  null      — không kiểm trường đó (vd router được phép route thừa)
  "absent"  — trường phải VẮNG (vd lượt hỏi chính sách thuần: order_node không được chạy)
  forbid_source — nguồn không được xuất hiện (vd khách khác không được thấy đơn của khách trước)
"""
from __future__ import annotations

import json
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"
GRAPH_CASES = EVAL_DIR / "graph_cases.jsonl"
GOLDEN = EVAL_DIR / "golden.jsonl"          # Day 66: bộ đề chính (ca độc lập)
CONVERSATIONS = EVAL_DIR / "conversation_cases.jsonl"


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def problems(out: dict, want: dict) -> list[str]:
    """Danh sách chỗ sai (rỗng = đúng) giữa kết quả ask() và mong đợi của một ca / một lượt."""
    found = []
    for key in ("route", "order_lookup"):
        expected = want.get(key)
        if expected is None:
            continue
        got = out.get(key)
        if (got is not None) if expected == "absent" else (got != expected):
            found.append(f"{key}={got} (mong đợi {expected})")
    forbid = want.get("forbid_source")
    if forbid and forbid in (out.get("sources") or []):
        found.append(f"lộ nguồn {forbid}")
    return found
