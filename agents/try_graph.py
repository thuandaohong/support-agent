"""Chạy graph thật (gọi AWS) trên eval/graph_cases.jsonl — các trường hợp biên của dữ liệu.

Tự kiểm phần TẤT ĐỊNH (route, order_lookup); câu trả lời thì in ra kèm "mong đợi" để người đọc
so bằng mắt. Chấm câu trả lời tự động (LLM-as-judge) để dành cho Phase E.

Chạy: python -m agents.try_graph            (tất cả)
      python -m agents.try_graph g05 g06    (chỉ vài câu)
"""
import json
import sys
from pathlib import Path

from agents.graph import ask

CASES = Path(__file__).resolve().parent.parent / "eval" / "graph_cases.jsonl"
AS_OF_DATE = "2026-11-08"   # cố định cho eval, không phụ thuộc .env


def main():
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line]
    wanted = set(sys.argv[1:])
    checked = passed = 0
    for c in cases:
        if wanted and c["id"] not in wanted:
            continue
        out = ask(c["question"], c["customer_id"], as_of_date=AS_OF_DATE)
        # null trong file = không kiểm trường đó (vd g11: router được phép route thừa)
        problems = []
        if c["route"] is not None and out.get("route") != c["route"]:
            problems.append(f"route={out.get('route')} (mong đợi {c['route']})")
        if c["order_lookup"] is not None and out.get("order_lookup") != c["order_lookup"]:
            problems.append(f"order_lookup={out.get('order_lookup')} (mong đợi {c['order_lookup']})")
        checked += 1
        passed += not problems

        print(f"── {c['id']} [{c['customer_id']}] {c['question']}")
        print(f"   route={out.get('route')} order_lookup={out.get('order_lookup', '-')} "
              f"steps={out['steps']} {'✅' if not problems else '❌ ' + '; '.join(problems)}")
        print(f"   MONG ĐỢI: {c['expect']}")
        print("   TRẢ LỜI : " + out["answer"].replace("\n", "\n             "))
        print(f"   NGUỒN   : {out.get('sources')}\n")
    print(f"Phần tất định (route + order_lookup): {passed}/{checked} đúng")


if __name__ == "__main__":
    main()
