"""eval/golden.jsonl (Day 66) — kiểm BỘ ĐỀ, không gọi AWS: đáp án phải khớp dữ liệu thật.

Golden sai thì eval đo sai mà không ai biết (vd ca "found" nhưng khách không phải chủ đơn → agent
trả not_found là ĐÚNG, eval lại chấm SAI). Test này đối chiếu từng ca với sample-data/.
"""
import csv
import re
from collections import Counter
from pathlib import Path

import pytest

from agents.eval_cases import GOLDEN, load
from agents.supervisor import VALID_ROUTES

ROOT = Path(__file__).resolve().parent.parent
POLICIES = {p.name for p in (ROOT / "sample-data" / "policies").glob("*.md")}
ORDERS = {r["order_id"]: r for r in
          csv.DictReader((ROOT / "sample-data" / "orders.csv").read_text(encoding="utf-8").splitlines())}
GROUPS = {"policy": "p", "order": "o", "multi": "m", "none": "n", "security": "s", "english": "e"}
LOOKUPS = {"found", "not_found", "no_id"}
REQUIRED = ("id", "group", "question", "customer_id", "route", "order_lookup", "order_id", "sources", "reference")
# invoke_runtime.py --auth đăng nhập Cognito bằng đúng khách của ca → khách phải là user test
TEST_USERS = set(re.search(r'TEST_USERS="([^"]+)"',
                           (ROOT / "infra" / "auth" / "auth.env.example").read_text()).group(1).split())

CASES = load(GOLDEN)


def test_du_ca_moi_nhom():
    assert len(CASES) >= 30
    counts = Counter(c["group"] for c in CASES)
    assert set(counts) == set(GROUPS)
    assert min(counts.values()) >= 4, counts


def test_id_khong_trung():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("c", CASES, ids=lambda c: c["id"])
def test_ca_khop_du_lieu(c):
    assert all(k in c for k in REQUIRED), set(REQUIRED) - set(c)
    assert c["id"].startswith(GROUPS[c["group"]])
    assert c["question"].strip() and c["reference"].strip()
    assert c["customer_id"] in TEST_USERS

    # route: đúng thứ tự chuẩn của parse_route(), không trùng
    assert c["route"] == [r for r in VALID_ROUTES if r in c["route"]]

    # order_lookup chỉ có nghĩa khi route có "order"
    if "order" in c["route"]:
        assert c["order_lookup"] in LOOKUPS
    else:
        assert c["order_lookup"] == "absent"

    order = ORDERS.get(c["order_id"] or "")
    if c["order_lookup"] == "found":
        assert order and order["customer_id"] == c["customer_id"], "ca found: khách phải là chủ đơn"
    elif c["order_lookup"] == "not_found":
        assert c["order_id"] and (order is None or order["customer_id"] != c["customer_id"])
    elif c["order_lookup"] == "no_id":
        assert c["order_id"] is None
    else:
        assert c["order_id"] is None

    # nguồn mong đợi phải có thật; orders/<id> chỉ khi tra được đúng đơn đó
    for s in c["sources"]:
        if s.startswith("orders/"):
            assert c["order_lookup"] == "found" and s == f"orders/{c['order_id']}"
        else:
            assert s in POLICIES, s
            assert "policy" in c["route"]

    forbid = c.get("forbid_source")
    if forbid:
        assert forbid not in c["sources"]
        assert forbid.startswith("orders/") and forbid[len("orders/"):] in ORDERS
