"""Test trí nhớ hội thoại (Day 62) — không gọi AWS, LLM và tool thay bằng hàm giả (fixture fake_aws).

Bước 1: reducer history + danh sách key reset mỗi lượt (chống State của lượt trước dính sang lượt sau).
"""
from agents.state import (
    HISTORY_TURNS,
    INPUT_KEYS,
    TURN_KEYS,
    SupportState,
    keep_last_turns,
)


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
