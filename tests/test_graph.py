"""Test graph + node mà KHÔNG gọi AWS: thay tool và LLM bằng hàm giả (monkeypatch).

Thứ được kiểm: luồng của graph (route nào chạy node nào, steps cộng đúng), 3 trạng thái tra đơn,
kết luận đổi trả/bảo hành gắn vào đơn, nguồn do code tạo. Chất lượng câu trả lời thật thì đo bằng agents/try_graph.py.
"""
import pytest

import agents.graph as graph_mod
from agents import nodes, supervisor
from tools.mcp_client import GatewayError

ORDERS = {  # "DynamoDB" giả: order_id → đơn
    "1003": {"order_id": "1003", "customer_id": "C003", "plan": "Premium",
             "status": "delivered", "order_date": "2026-11-02", "amount": 45},
}
HITS = [
    {"text": "Premium: 14 ngày", "source": "https://b.s3.amazonaws.com/policies/01-return-policy.md", "score": 0.5},
    {"text": "ví dụ", "source": "https://b.s3.amazonaws.com/policies/01-return-policy.md", "score": 0.4},
    {"text": "gói", "source": "https://b.s3.amazonaws.com/policies/03-service-plans.md", "score": 0.3},
]


@pytest.fixture
def fake_aws(monkeypatch):
    """Thay mọi lời gọi AWS. Trả dict `calls` để test xem node nào đã gọi gì."""
    calls = {"router_reply": '{"route": ["policy", "order"]}', "writer": 0, "search": 0}

    def fake_converse(model_id, system, user, max_tokens=512, temperature=0.0):
        if system is supervisor.ROUTER_PROMPT:          # router
            return calls["router_reply"], {}
        calls["writer"] += 1                            # writer
        calls["writer_input"] = user
        return "câu trả lời giả", {}

    def fake_search(query, top_k=3):
        calls["search"] += 1
        return HITS

    def fake_get_order(order_id, customer_id):
        order = ORDERS.get(order_id)
        # giống tool thật: đơn của người khác → None
        return dict(order) if order and order["customer_id"] == customer_id else None

    monkeypatch.setattr(supervisor, "converse_text", fake_converse)
    monkeypatch.setattr(nodes, "converse_text", fake_converse)
    monkeypatch.setattr(nodes, "search_policy", fake_search)
    monkeypatch.setattr(nodes, "get_order", fake_get_order)
    return calls


def run(question, customer="C003"):
    """Nguyên State cuối — test nội bộ cần xem order_data, policy_hits..."""
    return graph_mod.run_graph(question, customer, as_of_date="2026-11-08")


# ─── hợp đồng công khai của ask() (Day 57) ───

def test_ask_returns_only_public_fields(fake_aws):
    out = graph_mod.ask("Đơn #1003 còn đổi trả được không?", "C003", as_of_date="2026-11-08")
    assert set(out) == {"answer", "sources", "route", "order_lookup", "steps"}
    # chi tiết nội bộ không lọt ra: tên khách / số tiền / customer_id nằm trong order_data
    assert "order_data" not in out and "policy_hits" not in out and "customer_id" not in out


def test_ask_omits_fields_of_nodes_that_did_not_run(fake_aws):
    fake_aws["router_reply"] = '{"route": []}'
    out = graph_mod.ask("Xin chào", "C003", as_of_date="2026-11-08")
    assert set(out) == {"answer", "sources", "route", "steps"}   # order_node không chạy


def test_ask_passes_error_through_when_graph_is_stopped(fake_aws, monkeypatch):
    monkeypatch.setattr(graph_mod, "RECURSION_LIMIT", 2)
    out = graph_mod.ask("Đơn #1003 còn đổi trả được không?", "C003", as_of_date="2026-11-08")
    assert out["error"] == "recursion_limit" and "customer_id" not in out


# ─── luồng graph ───

def test_both_routes_run_in_parallel_and_steps_add_up(fake_aws):
    out = run("Đơn #1003 còn đổi trả được không?")
    assert out["route"] == ["policy", "order"]
    # supervisor 1 + (policy 1 + order 1, song song) + writer 1 = 4 → reducer cộng, không lỗi
    assert out["steps"] == 4
    assert out["order_lookup"] == "found"
    assert fake_aws["writer"] == 1                     # writer chạy đúng MỘT lần sau khi hội tụ
    assert out["sources"] == ["01-return-policy.md", "03-service-plans.md", "orders/1003"]


def test_policy_only_skips_order_node(fake_aws):
    fake_aws["router_reply"] = '{"route": ["policy"]}'
    out = run("Gói Premium đổi trả mấy ngày?")
    assert out["steps"] == 3
    assert "order_lookup" not in out                   # order_node không chạy
    assert "ORDER LOOKUP" not in fake_aws["writer_input"]


@pytest.mark.parametrize("question", ["Xin chào", "Cảm ơn bạn nhé", "Viết hàm Python sắp xếp list"])
def test_no_source_route_reaches_writer_without_llm(fake_aws, question):
    fake_aws["router_reply"] = '{"route": []}'
    out = run(question)
    assert out["steps"] == 2                           # supervisor + writer
    assert out["answer"].startswith("Chào bạn!")       # câu chào cố định (Day 56), tiếng Việt
    assert fake_aws["writer"] == 0 and fake_aws["search"] == 0   # không gọi LLM, không tra KB
    assert out["sources"] == []


def test_no_source_reply_follows_question_language(fake_aws):
    fake_aws["router_reply"] = '{"route": []}'
    assert run("hi").get("answer").startswith("Hi!")


def test_no_id_without_policy_asks_for_order_id_without_llm(fake_aws):
    fake_aws["router_reply"] = '{"route": ["order"]}'
    out = run("Tôi muốn hỏi về đơn hàng")
    assert out["order_lookup"] == "no_id" and out["steps"] == 3
    assert out["answer"].startswith("Bạn vui lòng cho mình xin mã đơn hàng")
    assert fake_aws["writer"] == 0                     # câu cố định, LLM không có cơ hội bịa
    assert run("Where is my order?").get("answer").startswith("Could you share your order number")


def test_no_id_with_policy_still_uses_llm(fake_aws):
    # router route thừa "order" cho câu chỉ hỏi chính sách (ca r16) → vẫn có đoạn chính sách để trả lời
    run("Tôi đặt hàng năm 2026, gói Pro đổi trả mấy ngày?")
    assert fake_aws["writer"] == 1
    assert "ORDER LOOKUP: no_id" in fake_aws["writer_input"]


def test_recursion_limit_returns_polite_answer(fake_aws, monkeypatch):
    # ép phanh cứng xuống 2 superstep: graph cần 3 (supervisor → policy ∥ order → writer)
    monkeypatch.setattr(graph_mod, "RECURSION_LIMIT", 2)
    out = run("Đơn #1003 còn đổi trả được không?")
    assert out["error"] == "recursion_limit"
    assert out["answer"].startswith("Xin lỗi, hệ thống đang bận")   # không ném exception ra ngoài
    assert fake_aws["writer"] == 0                     # bị chặn trước khi tới writer


# ─── order_node: 3 trạng thái ───

@pytest.mark.parametrize("question, customer, lookup", [
    ("Đơn #1003 tới đâu rồi?", "C003", "found"),
    ("Đơn #1003 tới đâu rồi?", "C020", "not_found"),   # đơn của người khác
    ("Đơn #9999 tới đâu rồi?", "C003", "not_found"),   # không tồn tại
    ("Đơn của tôi tới đâu rồi?", "C003", "no_id"),     # không có mã
])
def test_order_lookup_states(fake_aws, question, customer, lookup):
    fake_aws["router_reply"] = '{"route": ["order"]}'
    out = run(question, customer)
    assert out["order_lookup"] == lookup
    assert (out["order_data"] is not None) == (lookup == "found")


def test_order_node_attaches_code_computed_checks(fake_aws):
    out = nodes.order_node({"order_id": "1003", "customer_id": "C003", "as_of_date": "2026-11-08"})
    rc = out["order_data"]["return_check"]
    assert (rc["eligible"], rc["days_since_order"], rc["period_days"]) == (True, 6, 14)
    assert out["order_data"]["warranty_check"]["warranty_until"] == "2027-11-02"


# ─── hàm thuần ───

@pytest.mark.parametrize("question, lang", [
    ("Đơn #1003 còn đổi trả được không?", "vi"),
    ("Can I return order #1019?", "en"),
    ("don 1003 doi tra duoc khong", "en"),   # hạn chế đã biết: không dấu → coi là tiếng Anh
])
def test_question_language(question, lang):
    assert nodes.question_language(question) == lang


@pytest.mark.parametrize("answer, lang", [
    ("Đơn #1003 của bạn còn đổi trả được trong 14 ngày.", "vi"),
    ("You can return order #1036 (Bàn phím cơ) within 30 days.", "en"),  # tên SP có dấu vẫn là en
    ("Gói Premium được đổi trả trong vòng 14 ngày.", "vi"),            # lẫn từ tiếng Anh vẫn là vi
    ("", "en"),
])
def test_answer_language(answer, lang):
    assert nodes.answer_language(answer) == lang


def test_writer_retries_once_when_answer_language_is_wrong(fake_aws, monkeypatch):
    replies = iter(["The Pro plan allows returns within 30 days.", "Gói Pro được đổi trả trong 30 ngày."])
    sent = []

    def fake(model_id, system, user, **kw):
        sent.append(user)
        return next(replies), {}

    monkeypatch.setattr(nodes, "converse_text", fake)
    out = nodes.writer_node({"question": "Gói Pro đổi trả mấy ngày?", "route": ["policy"],
                             "policy_hits": HITS, "as_of_date": "2026-11-08"})
    assert out["answer"] == "Gói Pro được đổi trả trong 30 ngày."
    assert len(sent) == 2 and "wrong language" in sent[1]   # lần 2 đã đổi input


def test_writer_input_puts_language_instruction_last():
    text = nodes.build_writer_input({"question": "Can I return order #1003?", "as_of_date": "2026-11-08",
                                     "policy_hits": HITS, "order_lookup": "not_found"})
    assert text.endswith("Answer in English.")   # lệnh ngôn ngữ nằm cuối
    assert "ORDER LOOKUP: not_found" in text and "ORDER: " not in text


# ─── Day 60: hệ thống tra đơn hỏng (Gateway/Lambda) ───

@pytest.fixture
def broken_orders(fake_aws, monkeypatch):
    def broken(order_id, customer_id):
        raise GatewayError("unreachable")
    monkeypatch.setattr(nodes, "get_order", broken)
    return fake_aws


def test_order_backend_failure_is_error_not_not_found(broken_orders):
    out = nodes.order_node({"order_id": "1003", "customer_id": "C003", "as_of_date": "2026-11-08"})
    assert out["order_lookup"] == "error" and out["order_data"] is None


def test_order_backend_failure_answers_busy_without_llm(broken_orders):
    out = graph_mod.ask("Đơn #1003 còn đổi trả được không?", "C003", as_of_date="2026-11-08")
    assert out["order_lookup"] == "error" and out["error"] == "order_unavailable"
    assert out["answer"].startswith("Xin lỗi, hệ thống tra cứu đơn hàng đang bận")
    assert "không tìm thấy" not in out["answer"].lower()
    assert out["sources"] == [] and broken_orders["writer"] == 0   # không gọi LLM writer


# ─── Day 61: hệ thống tra chính sách hỏng ───

@pytest.fixture
def broken_policy(fake_aws, monkeypatch):
    def broken(query, top_k=3):
        raise GatewayError("tool_kb_unavailable")
    monkeypatch.setattr(nodes, "search_policy", broken)
    return fake_aws


def test_policy_backend_failure_is_error_not_empty(broken_policy):
    out = nodes.policy_node({"question": "Gói Pro đổi trả mấy ngày?"})
    assert out["policy_lookup"] == "error" and out["policy_hits"] == []


def test_policy_ok_marks_lookup(fake_aws):
    assert nodes.policy_node({"question": "Gói Pro đổi trả mấy ngày?"})["policy_lookup"] == "ok"


def test_policy_failure_answers_busy_without_llm(broken_policy):
    broken_policy["router_reply"] = '{"route": ["policy"]}'
    out = graph_mod.ask("Gói Pro đổi trả mấy ngày?", "C003", as_of_date="2026-11-08")
    assert out["error"] == "policy_unavailable"
    assert out["answer"].startswith("Xin lỗi, hệ thống tra cứu chính sách đang bận")
    assert out["sources"] == [] and broken_policy["writer"] == 0


def test_policy_failure_wins_over_asking_order_id(broken_policy):
    # route thừa "order" + câu không có mã đơn (ca r16): chính sách hỏng → báo bận, KHÔNG xin mã đơn
    out = graph_mod.ask("Tôi mới đặt hàng, gói Basic có được miễn phí vận chuyển không?", "C003",
                        as_of_date="2026-11-08")
    assert out["order_lookup"] == "no_id" and out["error"] == "policy_unavailable"


def test_both_sources_failing_gives_one_busy_answer(broken_policy, monkeypatch):
    def broken_order(order_id, customer_id):
        raise GatewayError("http_403")
    monkeypatch.setattr(nodes, "get_order", broken_order)
    out = graph_mod.ask("Đơn #1003 còn đổi trả được không?", "C003", as_of_date="2026-11-08")
    assert out["error"] == "tools_unavailable"
    assert out["answer"].startswith("Xin lỗi, hệ thống tra cứu đang bận")
