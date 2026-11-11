"""Ráp 4 node thành StateGraph và chạy end-to-end.

    START → supervisor ──route──┬─► policy ─┐
                                ├─► order  ─┼─► writer → END
                                └───────────┘   (route rỗng: đi thẳng tới writer)

Chạy: python -m agents.graph "Đơn #1003 còn đổi trả được không?" --customer C003
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import date

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from agents.nodes import order_node, policy_node, writer_node
from agents.state import SupportState
from agents.supervisor import supervisor_node

load_dotenv()
# "Hôm nay" để tính hạn đổi trả. Eval cố định 2026-11-08 (xem sample-data/README.md); bỏ trống
# biến này trong .env thì dùng ngày thật (demo).
AS_OF_DATE = os.environ.get("AS_OF_DATE") or None

# Chặn graph chạy quá số bước (phòng vòng lặp đốt tiền). Graph này không có vòng lặp, chạy tối đa
# 4 node, nên 10 là dư — chủ yếu là lưới an toàn khi Day sau thêm cạnh quay lui.
RECURSION_LIMIT = 10


def route_after_supervisor(state: SupportState) -> list[str]:
    """Quyết định chạy node nào sau supervisor (hàm cho conditional edge).

    - Trả LIST nhiều tên → LangGraph chạy các node đó SONG SONG (fan-out).
    - route rỗng (câu ngoài phạm vi) → phải đi tới "writer" để còn trả lời từ chối. Nếu trả list
      rỗng, LangGraph coi như không có node tiếp theo → graph dừng ngay sau supervisor, người dùng
      không nhận được câu trả lời nào (đã thử, Day 55 — bài gốc dính lỗi này).
    """
    return state.get("route") or ["writer"]


def build_graph():
    """Dựng và compile graph. Tên node ("policy", "order") trùng với giá trị trong route."""
    g = StateGraph(SupportState)

    # 1. Đăng ký node: tên → hàm
    g.add_node("supervisor", supervisor_node)
    g.add_node("policy", policy_node)
    g.add_node("order", order_node)
    g.add_node("writer", writer_node)

    # 2. Nối dây
    g.add_edge(START, "supervisor")
    # Cạnh có điều kiện: sau supervisor, gọi route_after_supervisor để biết đi đâu.
    # Tham số thứ 3 khai báo trước MỌI đích có thể tới — LangGraph dùng để kiểm tra và vẽ sơ đồ.
    g.add_conditional_edges("supervisor", route_after_supervisor, ["policy", "order", "writer"])
    # Hai nhánh HỘI TỤ về writer (fan-in). Nếu cả hai cùng chạy, chúng ở cùng một "superstep";
    # writer chỉ chạy ở superstep kế tiếp, khi cả hai đã xong → writer chạy ĐÚNG MỘT LẦN và thấy
    # đủ policy_hits + order_data. Không phải tự viết logic chờ.
    g.add_edge("policy", "writer")
    g.add_edge("order", "writer")
    g.add_edge("writer", END)

    # 3. compile: kiểm tra graph hợp lệ (node nào cũng tới được, cạnh trỏ đúng tên...) → app chạy được
    return g.compile()


# Compile một lần khi import, mọi lần ask() dùng lại (giống cách tạo boto3 client một lần)
graph = build_graph()


def ask(question: str, customer_id: str, as_of_date: str | None = None) -> dict:
    """Chạy graph cho 1 câu hỏi, trả State cuối (answer, sources, route, order_lookup, steps...).

    customer_id: phía gọi (API sau này) lấy từ danh tính đã đăng nhập, không từ câu hỏi.
    as_of_date: "hôm nay" dạng YYYY-MM-DD; None → AS_OF_DATE trong .env → ngày thật.
    """
    initial = {
        "question": question,
        "customer_id": customer_id,
        "as_of_date": as_of_date or AS_OF_DATE or date.today().isoformat(),
        "steps": 0,   # điểm xuất phát cho reducer operator.add
    }
    return graph.invoke(initial, config={"recursion_limit": RECURSION_LIMIT})


def main():
    parser = argparse.ArgumentParser(description="Hỏi support-agent một câu.")
    parser.add_argument("question")
    parser.add_argument("--customer", required=True, help="customer_id, vd C003")
    parser.add_argument("--as-of", help="ngày 'hôm nay' YYYY-MM-DD (mặc định AS_OF_DATE)")
    parser.add_argument("-v", "--verbose", action="store_true", help="in log của các node")
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

    out = ask(args.question, args.customer, args.as_of)
    print(f"ROUTE: {out.get('route')}   ORDER_LOOKUP: {out.get('order_lookup', '-')}   "
          f"STEPS: {out['steps']}")
    if out.get("order_data"):
        print("ORDER:", json.dumps(out["order_data"], ensure_ascii=False))
    print(f"\nTRẢ LỜI:\n{out['answer']}\n\nNGUỒN: {out.get('sources')}")


if __name__ == "__main__":
    main()
