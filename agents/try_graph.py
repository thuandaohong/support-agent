"""Chạy graph thật (gọi AWS) trên bộ eval — các trường hợp biên của dữ liệu.

Tự kiểm phần TẤT ĐỊNH (route, order_lookup); câu trả lời thì in ra kèm "mong đợi" để người đọc
so bằng mắt. Chấm câu trả lời tự động (LLM-as-judge) để dành cho Phase E.

Chạy: python -m agents.try_graph            (eval/graph_cases.jsonl — mỗi câu độc lập)
      python -m agents.try_graph g05 g06    (chỉ vài câu)
      python -m agents.try_graph --chat     (eval/conversation_cases.jsonl — hội thoại nhiều lượt, Day 62)
"""
import sys
import uuid

from agents.eval_cases import CONVERSATIONS, GRAPH_CASES, load, problems
from agents.graph import ask

AS_OF_DATE = "2026-11-08"   # cố định cho eval, không phụ thuộc .env


def show(label: str, question: str, out: dict, bad: list[str], expect: str | None) -> None:
    print(f"── {label} {question}")
    print(f"   route={out.get('route')} order_lookup={out.get('order_lookup', '-')} "
          f"steps={out['steps']} {'✅' if not bad else '❌ ' + '; '.join(bad)}")
    if expect:
        print(f"   MONG ĐỢI: {expect}")
    print("   TRẢ LỜI : " + out["answer"].replace("\n", "\n             "))
    print(f"   NGUỒN   : {out.get('sources')}\n")


def run_cases(wanted: set[str]) -> None:
    checked = passed = 0
    for c in load(GRAPH_CASES):
        if wanted and c["id"] not in wanted:
            continue
        # không truyền session_id → mỗi câu độc lập, không dính lịch sử của câu trước
        out = ask(c["question"], c["customer_id"], as_of_date=AS_OF_DATE)
        bad = problems(out, c)
        checked += 1
        passed += not bad
        show(f"{c['id']} [{c['customer_id']}]", c["question"], out, bad, c.get("expect"))
    print(f"Phần tất định (route + order_lookup): {passed}/{checked} đúng")


def run_conversations(wanted: set[str]) -> None:
    checked = passed = 0
    for conv in load(CONVERSATIONS):
        if wanted and conv["id"] not in wanted:
            continue
        print(f"═══ {conv['id']}: {conv['note']}")
        session = f"chat-{conv['id']}-{uuid.uuid4().hex}"     # mỗi hội thoại một session
        for i, turn in enumerate(conv["turns"], 1):
            customer = turn.get("customer_id", conv["customer_id"])
            out = ask(turn["q"], customer, as_of_date=AS_OF_DATE, session_id=session)
            bad = problems(out, turn)
            checked += 1
            passed += not bad
            show(f"lượt {i} [{customer}]", turn["q"], out, bad, turn.get("expect"))
    print(f"Hội thoại — phần tất định (route + order_lookup + nguồn): {passed}/{checked} lượt đúng")


def main():
    args = sys.argv[1:]
    if args[:1] == ["--chat"]:
        run_conversations(set(args[1:]))
    else:
        run_cases(set(args))


if __name__ == "__main__":
    main()
