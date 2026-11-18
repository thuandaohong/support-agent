"""Tóm tắt Terraform plan AN TOÀN để đăng công khai (Day 65): comment PR + log Actions của repo public.

`terraform plan` in nguyên giá trị (account id, pool id, KB id, ARN, `imported from "<id>"`) → không được
dán vào PR / log như Project 1. Script này chỉ in: địa chỉ resource, hành động, TÊN thuộc tính đổi — không
in giá trị, không in import id.

Plan có xoá (delete) hoặc xoá-rồi-tạo-lại (replace) → exit 1 (chặn merge), trừ khi ALLOW_DESTROY=1.

Chạy:  terraform show -json tfplan | python scripts/tf_plan_summary.py > summary.md
"""
from __future__ import annotations

import json
import os
import sys

ICON = {"import": "📥", "create": "➕", "update": "✏️", "delete": "❌", "replace": "♻️"}


def classify(rc: dict) -> list[str]:
    """Các hành động của một resource: import có thể đi kèm update."""
    actions = rc["change"]["actions"]
    kinds = []
    if rc["change"].get("importing"):
        kinds.append("import")
    if actions == ["create"]:
        kinds.append("create")
    elif actions == ["update"]:
        kinds.append("update")
    elif actions == ["delete"]:
        kinds.append("delete")
    elif set(actions) == {"create", "delete"}:
        kinds.append("replace")
    return kinds


def changed_attrs(change: dict) -> list[str]:
    """Tên thuộc tính cấp 1 khác nhau giữa before / after (kể cả giá trị chưa biết lúc plan)."""
    before, after = change.get("before") or {}, change.get("after") or {}
    unknown = change.get("after_unknown") or {}
    keys = set(before) | set(after) | {k for k, v in unknown.items() if v}
    return sorted(k for k in keys if before.get(k) != after.get(k) or unknown.get(k) is True)


def summarize(plan: dict) -> tuple[str, dict[str, int]]:
    counts = dict.fromkeys(ICON, 0)
    rows = []
    for rc in plan.get("resource_changes", []):
        if rc.get("mode") != "managed":
            continue
        kinds = classify(rc)
        if not kinds:
            continue
        for k in kinds:
            counts[k] += 1
        attrs = changed_attrs(rc["change"]) if {"update", "replace"} & set(kinds) else []
        # last_modified của Lambda luôn "chưa biết" khi đổi code — nhiễu, không cần đọc
        attrs = [a for a in attrs if a not in ("last_modified", "tags_all")] + \
                (["tags"] if "tags_all" in changed_attrs(rc["change"]) else [])
        rows.append((rc["address"], " ".join(f"{ICON[k]} {k}" for k in kinds), ", ".join(attrs)))

    head = (f"**{counts['import']} import · {counts['create']} create · {counts['update']} update · "
            f"{counts['replace']} replace · {counts['delete']} delete**")
    lines = [head, ""]
    if rows:
        lines += ["| resource | hành động | thuộc tính đổi (không in giá trị) |", "|---|---|---|"]
        lines += [f"| `{a}` | {k} | {c} |" for a, k, c in rows]
    else:
        lines.append("No changes — hạ tầng khớp code.")
    return "\n".join(lines), counts


def main() -> int:
    md, counts = summarize(json.load(sys.stdin))
    danger = counts["delete"] + counts["replace"]
    if danger and os.environ.get("ALLOW_DESTROY") != "1":
        md += (f"\n\n> ⛔ Plan có {danger} resource bị xoá / tạo lại. Kiểm lại code (thuộc tính `forces replacement`) "
               "hoặc chạy lại với ALLOW_DESTROY=1 nếu thật sự muốn.")
        print(md)
        return 1
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
