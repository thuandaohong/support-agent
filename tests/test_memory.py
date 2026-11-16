"""Test trí nhớ hội thoại (Day 62) — không gọi AWS, LLM và tool thay bằng hàm giả (fixture fake_aws).

Bước 1: reducer history + danh sách key reset mỗi lượt (chống State của lượt trước dính sang lượt sau).
Bước 2: checkpointer + thread_id = khách + session.
Bước 3: supervisor đọc lịch sử (router + mã đơn).
"""
import agents.graph as graph_mod
from agents import nodes, supervisor
from agents.state import (
    HISTORY_TURNS,
    INPUT_KEYS,
    TURN_KEYS,
    SupportState,
    keep_last_turns,
)
from tools.mcp_client import GatewayError


def turn(i):
    return {"q": f"câu {i}", "a": f"đáp {i}", "order_id": None}


def test_history_reducer_appends_and_keeps_last_turns():
    assert keep_last_turns(None, [turn(1)]) == [turn(1)]
    assert keep_last_turns([turn(1)], None) == [turn(1)]
    many = keep_last_turns([turn(i) for i in range(HISTORY_TURNS)], [turn(99)])
    assert len(many) == HISTORY_TURNS and many[-1] == turn(99) and many[0] == turn(1)


def test_every_state_key_is_input_turn_or_memory():
    # Thêm key mới vào SupportState mà quên xếp loại → test đỏ. Key theo lượt mà không reset thì
    # giá trị của lượt trước dính sang lượt sau khi có checkpointer (day62-plan, lỗi số 5).
    keys = set(SupportState.__annotations__)
    assert keys == set(INPUT_KEYS) | set(TURN_KEYS) | {"steps", "history"}
    assert not set(INPUT_KEYS) & set(TURN_KEYS)


def test_run_graph_resets_turn_keys(fake_aws):
    from agents import graph as graph_mod
    fake_aws["router_reply"] = '{"route": ["policy"]}'
    out = graph_mod.run_graph("Gói Premium đổi trả mấy ngày?", "C003", as_of_date="2026-11-08")
    assert all(k in out for k in TURN_KEYS)            # đều có mặt (None nếu lượt này không ghi)
    assert out["order_lookup"] is None and out["steps"] == 3


# ─── Bước 2: checkpointer + thread_id ───


def chat(question, customer="C003", session="s1"):
    return graph_mod.run_graph(question, customer, as_of_date="2026-11-08", session_id=session)


def test_same_session_remembers_previous_turns(fake_aws):
    chat("Đơn #1003 còn đổi trả được không?")
    out = chat("Thế bảo hành thì sao?")
    assert [h["q"] for h in out["history"]] == ["Đơn #1003 còn đổi trả được không?", "Thế bảo hành thì sao?"]
    assert out["history"][0]["order_id"] == "1003"          # mã do code rút, lưu kèm lượt
    assert out["history"][0]["a"] == "câu trả lời giả"


def test_other_session_or_other_customer_starts_blank(fake_aws):
    chat("Đơn #1003 còn đổi trả được không?", session="s-mem")
    assert len(chat("xin chào", session="s-khac")["history"]) == 1
    # cùng session id nhưng KHÁC khách → khoá khác → không đọc được lịch sử của C003
    assert len(chat("xin chào", customer="C020", session="s-mem")["history"]) == 1


def test_previous_turn_error_does_not_leak_into_next_turn(fake_aws, monkeypatch):
    def broken(order_id, customer_id):
        raise GatewayError("http_403")
    monkeypatch.setattr(nodes, "get_order", broken)
    first = chat("Đơn #1003 còn đổi trả được không?", session="s-err")
    assert first["error"] == "order_unavailable"

    fake_aws["router_reply"] = '{"route": ["policy"]}'
    second = chat("Gói Premium đổi trả mấy ngày?", session="s-err")
    # Không reset key theo lượt thì order_lookup="error" + error của lượt 1 còn đó → "đang bận" mãi
    assert second.get("error") is None and second["order_lookup"] is None
    assert second["answer"] == "câu trả lời giả" and second["steps"] == 3


def test_fixed_answers_are_recorded_too(fake_aws):
    fake_aws["router_reply"] = '{"route": []}'
    out = chat("Xin chào", session="s-fixed")
    assert out["history"][-1]["a"].startswith("Chào bạn!")   # nhánh câu cố định vẫn ghi lịch sử


def test_no_session_means_no_memory_and_nothing_kept(fake_aws):
    graph_mod.run_graph("Đơn #1003?", "C777", as_of_date="2026-11-08")
    out = graph_mod.run_graph("Thế bảo hành?", "C777", as_of_date="2026-11-08")
    assert len(out["history"]) == 1
    assert not [t for t in graph_mod._checkpointer.storage if t.startswith("C777:")]   # thread lẻ đã xoá


def test_ask_accepts_session_and_keeps_public_contract(fake_aws):
    graph_mod.ask("Đơn #1003 còn đổi trả được không?", "C003", as_of_date="2026-11-08", session_id="s-ask")
    out = graph_mod.ask("Thế bảo hành thì sao?", "C003", as_of_date="2026-11-08", session_id="s-ask")
    assert "history" not in out and set(out) <= set(graph_mod.PUBLIC_FIELDS)


# ─── Bước 3: supervisor dùng lịch sử ───


H1003 = [{"q": "Đơn #1003 còn đổi trả được không?", "a": "Còn.", "order_id": "1003"}]


def route_with(fake_aws, question, history, reply):
    fake_aws["router_reply"] = reply
    return supervisor.supervisor_node({"question": question, "customer_id": "C003", "history": history})


def test_router_sees_previous_questions_not_answers(fake_aws):
    route_with(fake_aws, "Thế bảo hành thì sao?", H1003, '{"route": ["policy", "order"]}')
    sent = fake_aws["router_input"]
    assert "<history>\n- Đơn #1003 còn đổi trả được không?\n</history>" in sent
    assert "Còn." not in sent and sent.endswith("<question>Thế bảo hành thì sao?</question>")


def test_no_history_router_input_unchanged(fake_aws):
    route_with(fake_aws, "Gói Pro đổi trả mấy ngày?", [], '{"route": ["policy"]}')
    assert fake_aws["router_input"] == "<question>Gói Pro đổi trả mấy ngày?</question>"


def test_follow_up_takes_order_id_from_history(fake_aws):
    out = route_with(fake_aws, "Thế bảo hành thì sao?", H1003, '{"route": ["policy", "order"]}')
    assert out["order_id"] == "1003"


def test_new_order_id_in_question_wins(fake_aws):
    out = route_with(fake_aws, "Còn đơn #1019 thì sao?", H1003, '{"route": ["policy", "order"]}')
    assert out["order_id"] == "1019"


def test_history_order_id_only_when_order_route(fake_aws):
    out = route_with(fake_aws, "Gói Basic có miễn phí ship không?", H1003, '{"route": ["policy"]}')
    assert out["order_id"] is None                       # chuyển chủ đề → không kéo mã cũ theo


def test_bare_number_is_order_id_only_after_bot_asked(fake_aws):
    asked = [{"q": "Đơn của tôi bao giờ tới?", "a": "Cho mình xin mã đơn", "order_id": None,
              "asked_order_id": True}]
    out = route_with(fake_aws, "1003", asked, '{"route": []}')   # router không hiểu "1003" đứng một mình
    assert out["order_id"] == "1003" and "order" in out["route"]
    out = route_with(fake_aws, "1003", [{"q": "Xin chào", "a": "Chào", "order_id": None}], '{"route": []}')
    assert out["order_id"] is None and out["route"] == []   # không xin mã trước → con số trơn không là mã


def test_asking_for_order_id_is_recorded(fake_aws):
    fake_aws["router_reply"] = '{"route": ["order"]}'
    out = chat("Đơn của tôi bao giờ tới?", session="s-ask-id")
    assert out["history"][-1]["asked_order_id"] is True
    out = chat("1003", session="s-ask-id")
    assert out["order_lookup"] == "found" and out["order_id"] == "1003"
