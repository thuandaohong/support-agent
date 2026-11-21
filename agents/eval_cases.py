"""Đọc bộ eval + chấm phần TẤT ĐỊNH — dùng chung cho agents/try_graph.py (local) và
scripts/invoke_runtime.py (qua AgentCore Runtime), để hai nơi chấm cùng một luật.

golden.jsonl             — mỗi dòng 1 câu hỏi độc lập (Day 66: gộp graph_cases + routing_cases)
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


# ---------- Day 66: chấm từng ca golden + bảng theo nhóm (dùng chung cho run_eval local / runtime) ----------
LOOKUPS = ("found", "not_found", "no_id")
METRICS = ("routing", "lookup", "sources", "ok")


def score(out: dict, case: dict) -> dict:
    """Chấm một ca. Mỗi *_ok là True / False, hoặc None khi ca không kiểm tiêu chí đó.

    routing: route đúng NGUYÊN list (parse_route đã chuẩn hoá thứ tự → không dùng set).
    lookup:  chỉ tính ca có tra đơn (found / not_found / no_id); "absent" vẫn vào problems.
    sources: recall — mọi nguồn mong đợi phải có (KB trả top 3, thừa nguồn không sai) + không có forbid_source.
    ok:      không có chỗ sai nào (kể cả agent trả error).
    """
    found = problems(out, case)
    got = out.get("sources") or []
    missing = [s for s in case.get("sources") or [] if s not in got]
    found += [f"thiếu nguồn {s}" for s in missing]
    if out.get("error"):
        found.append(f"error={out['error']}")
    forbid = case.get("forbid_source")
    checks_sources = bool(case.get("sources")) or bool(forbid)
    return {
        "routing": None if case.get("route") is None else out.get("route") == case["route"],
        "lookup": out.get("order_lookup") == case["order_lookup"] if case.get("order_lookup") in LOOKUPS else None,
        "sources": (not missing and forbid not in got) if checks_sources else None,
        "ok": not found,
        "problems": found,
    }


def summarize(rows: list[tuple[dict, dict]]) -> dict[str, dict[str, list[int]]]:
    """[(case, score)] → {nhóm: {metric: [đạt, tổng]}} + nhóm "TỔNG". Metric None không tính vào tổng."""
    table: dict[str, dict[str, list[int]]] = {}
    for case, sc in rows:
        for group in (case["group"], "TỔNG"):
            cell = table.setdefault(group, {m: [0, 0] for m in METRICS})
            for m in METRICS:
                if sc[m] is not None:
                    cell[m][0] += bool(sc[m])
                    cell[m][1] += 1
    total = table.pop("TỔNG", {m: [0, 0] for m in METRICS})
    return {**dict(sorted(table.items())), "TỔNG": total}


def format_table(table: dict[str, dict[str, list[int]]]) -> str:
    head = f"{'nhóm':<10}{'routing':>10}{'tra đơn':>10}{'nguồn':>10}{'đạt hết':>10}"
    lines = [head, "-" * len(head)]
    for group, cell in table.items():
        vals = "".join(f"{(f'{p}/{n}' if n else '-'):>10}" for p, n in (cell[m] for m in METRICS))
        lines.append(f"{group:<10}{vals}")
    return "\n".join(lines)


def rate(cell: list[int]) -> float:
    return cell[0] / cell[1] if cell[1] else 1.0
