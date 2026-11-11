"""Đo routing accuracy của supervisor trên eval/routing_cases.jsonl (gọi LLM thật).

Chạy: python -m agents.try_supervisor
"""
import json
from pathlib import Path

from agents.supervisor import ROUTER_MODEL_ID, supervisor_node

CASES = Path(__file__).resolve().parent.parent / "eval" / "routing_cases.jsonl"


def main():
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line]
    passed = 0
    for c in cases:
        out = supervisor_node({"question": c["question"], "customer_id": "C000"})
        ok = out["route"] == c["route"] and out["order_id"] == c["order_id"]
        passed += ok
        mark = "✅" if ok else f"❌ (mong đợi route={c['route']} order_id={c['order_id']})"
        print(f"{c['id']}  route={out['route']!s:<20} order_id={out['order_id']!s:<5} {mark}")
    print(f"\nRouting accuracy: {passed}/{len(cases)} = {passed / len(cases):.0%}  ({ROUTER_MODEL_ID})")


if __name__ == "__main__":
    main()
