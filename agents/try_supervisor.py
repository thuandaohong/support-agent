"""Đo routing accuracy CHỈ của supervisor trên eval/golden.jsonl (gọi LLM thật, rẻ: không chạy tool / writer).

Cả graph + chấm nguồn + lưu file: scripts/run_eval.py (Day 66).

Chạy: python -m agents.try_supervisor
"""
from agents.eval_cases import GOLDEN, load
from agents.supervisor import ROUTER_MODEL_ID, supervisor_node


def main():
    cases = load(GOLDEN)
    passed = 0
    for c in cases:
        out = supervisor_node({"question": c["question"], "customer_id": c["customer_id"]})
        ok = out["route"] == c["route"] and out["order_id"] == c["order_id"]
        passed += ok
        mark = "✅" if ok else f"❌ (mong đợi route={c['route']} order_id={c['order_id']})"
        print(f"{c['id']}  route={out['route']!s:<20} order_id={out['order_id']!s:<5} {mark}")
    print(f"\nRouting accuracy: {passed}/{len(cases)} = {passed / len(cases):.0%}  ({ROUTER_MODEL_ID})")


if __name__ == "__main__":
    main()
