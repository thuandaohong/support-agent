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
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph

from agents.nodes import order_node, policy_node, question_language, writer_node
from agents.state import SupportState
from agents.supervisor import supervisor_node

load_dotenv()
# "Hôm nay" để tính hạn đổi trả. Eval cố định 2026-11-08 (xem sample-data/README.md); bỏ trống
# biến này trong .env thì dùng ngày thật (demo).
AS_OF_DATE = os.environ.get("AS_OF_DATE") or None

log = logging.getLogger(__name__)

# Chặn graph chạy quá số SUPERSTEP (phòng vòng lặp đốt tiền). Graph này không có vòng lặp, tối đa
# 3 superstep (supervisor → policy ∥ order → writer), nên 10 là dư — lưới an toàn khi Day sau thêm
# cạnh quay lui. Vượt giới hạn: LangGraph ném GraphRecursionError → ask() bắt, trả câu lịch sự.
RECURSION_LIMIT = 10

# Câu trả khi graph bị chặn giữa chừng — khách vẫn nhận được câu trả lời thay vì lỗi 500
_BUSY = {
    "vi": "Xin lỗi, hệ thống đang bận nên chưa trả lời được. Bạn vui lòng thử lại sau ít phút nhé.",
    "en": "Sorry, the system is busy and couldn't answer right now. Please try again in a few minutes.",
}


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


# Các trường ask() trả ra ngoài — HỢP ĐỒNG với người gọi (API Phase D, eval Phase E).
#   answer, sources: hiển thị cho khách;  route, order_lookup: đo routing / tra đơn (eval);
#   steps: theo dõi chi phí;  error: chỉ có khi không trả lời bình thường được ("recursion_limit",
#   "order_unavailable" — hệ thống tra đơn hỏng, Day 60).
# KHÔNG trả order_data (tên khách, số tiền, customer_id), policy_hits (nguyên văn tài liệu),
# question... — đó là chi tiết nội bộ: lộ ra API là lộ dữ liệu, và người gọi sẽ phụ thuộc vào cấu
# trúc State, đổi graph là vỡ người gọi.
PUBLIC_FIELDS = ("answer", "sources", "route", "order_lookup", "steps", "error")


def ask(question: str, customer_id: str, as_of_date: str | None = None) -> dict:
    """CỬA VÀO DUY NHẤT của agent: 1 câu hỏi → dict công khai (xem PUBLIC_FIELDS).

    customer_id: phía gọi (API sau này) lấy từ danh tính đã đăng nhập, không từ câu hỏi.
    as_of_date: "hôm nay" dạng YYYY-MM-DD; None → AS_OF_DATE trong .env → ngày thật.
    Trường nào không có trong lần chạy (vd route ["policy"] → không có order_lookup) thì vắng mặt.
    """
    state = run_graph(question, customer_id, as_of_date)
    return {k: state[k] for k in PUBLIC_FIELDS if k in state}


def run_graph(question: str, customer_id: str, as_of_date: str | None = None) -> dict:
    """Chạy graph, trả NGUYÊN State cuối (có order_data, policy_hits...) — cho debug và test.

    Code gọi từ bên ngoài (API, eval) dùng ask(), không dùng hàm này.
    """
    initial = {
        "question": question,
        "customer_id": customer_id,
        "as_of_date": as_of_date or AS_OF_DATE or date.today().isoformat(),
        "steps": 0,   # điểm xuất phát cho reducer operator.add
    }
    try:
        return graph.invoke(initial, config={"recursion_limit": RECURSION_LIMIT})
    except GraphRecursionError:
        # Hai tầng phanh (Day 56): recursion_limit là phanh CỨNG của LangGraph — ném exception.
        # Bắt ở đây để thoát LỊCH SỰ: khách nhận câu "hệ thống bận", log cảnh báo để mình biết
        # có vòng lặp bất thường (không log nội dung câu hỏi). Tầng mềm — conditional edge kiểm
        # `steps < N` để tự thoát kèm câu trả lời — chỉ cần khi graph có vòng lặp.
        log.warning("graph stopped: recursion_limit=%d exceeded", RECURSION_LIMIT)
        return {**initial, "answer": _BUSY[question_language(question)], "sources": [],
                "error": "recursion_limit"}


def main():
    parser = argparse.ArgumentParser(description="Hỏi support-agent một câu.")
    parser.add_argument("question")
    parser.add_argument("--customer", required=True, help="customer_id, vd C003")
    parser.add_argument("--as-of", help="ngày 'hôm nay' YYYY-MM-DD (mặc định AS_OF_DATE)")
    parser.add_argument("-v", "--verbose", action="store_true", help="in log của các node")
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

    out = run_graph(args.question, args.customer, args.as_of)   # nguyên State để in ORDER khi debug
    print(f"ROUTE: {out.get('route')}   ORDER_LOOKUP: {out.get('order_lookup', '-')}   "
          f"STEPS: {out['steps']}")
    if out.get("order_data"):
        print("ORDER:", json.dumps(out["order_data"], ensure_ascii=False))
    print(f"\nTRẢ LỜI:\n{out['answer']}\n\nNGUỒN: {out.get('sources')}")


if __name__ == "__main__":
    main()
