"""agents/eval_cases.score / summarize (Day 66) — luật chấm golden, không gọi AWS."""
from agents.eval_cases import format_table, rate, score, summarize

MULTI = {"id": "m01", "group": "multi", "route": ["policy", "order"], "order_lookup": "found",
         "sources": ["01-return-policy.md", "orders/1003"]}
POLICY = {"id": "p01", "group": "policy", "route": ["policy"], "order_lookup": "absent", "sources": ["01-return-policy.md"]}
SECURITY = {"id": "s02", "group": "security", "route": ["order"], "order_lookup": "not_found", "sources": [],
            "forbid_source": "orders/1003"}
NONE = {"id": "n01", "group": "none", "route": [], "order_lookup": "absent", "sources": []}

GOOD_MULTI = {"route": ["policy", "order"], "order_lookup": "found",
              "sources": ["01-return-policy.md", "05-faq.md", "orders/1003"]}


def test_dung_het_nguon_thua_khong_sai():
    sc = score(GOOD_MULTI, MULTI)
    assert sc == {"routing": True, "lookup": True, "sources": True, "ok": True, "problems": []}


def test_route_so_nguyen_list():
    sc = score({**GOOD_MULTI, "route": ["order"]}, MULTI)
    assert sc["routing"] is False and not sc["ok"]


def test_thieu_nguon():
    sc = score({**GOOD_MULTI, "sources": ["orders/1003"]}, MULTI)
    assert sc["sources"] is False and "thiếu nguồn 01-return-policy.md" in sc["problems"]


def test_absent_khong_tinh_lookup_nhung_van_sai():
    sc = score({"route": ["policy"], "order_lookup": "no_id", "sources": ["01-return-policy.md"]}, POLICY)
    assert sc["lookup"] is None and sc["routing"] is True and not sc["ok"]


def test_forbid_source():
    sc = score({"route": ["order"], "order_lookup": "not_found", "sources": ["orders/1003"]}, SECURITY)
    assert sc["sources"] is False and sc["lookup"] is True and not sc["ok"]


def test_khong_kiem_nguon_khi_khong_mong_doi():
    sc = score({"route": [], "sources": []}, NONE)
    assert sc["sources"] is None and sc["lookup"] is None and sc["ok"]


def test_agent_tra_error_la_sai():
    sc = score({**GOOD_MULTI, "error": "tools_unavailable"}, MULTI)
    assert not sc["ok"] and "error=tools_unavailable" in sc["problems"]


def test_bang_theo_nhom():
    rows = [(MULTI, score(GOOD_MULTI, MULTI)), (MULTI, score({**GOOD_MULTI, "route": ["order"]}, MULTI)),
            (NONE, score({"route": []}, NONE))]
    table = summarize(rows)
    assert list(table) == ["multi", "none", "TỔNG"]
    assert table["multi"]["routing"] == [1, 2] and table["none"]["sources"] == [0, 0]
    assert table["TỔNG"]["routing"] == [2, 3] and table["TỔNG"]["ok"] == [2, 3]
    assert rate(table["TỔNG"]["routing"]) == 2 / 3 and rate([0, 0]) == 1.0
    out = format_table(table)
    assert "TỔNG" in out and "2/3" in out and out.splitlines()[3].split()[3] == "-"
