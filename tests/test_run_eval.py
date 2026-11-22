"""scripts/run_eval.py (Day 66) — harness với agent giả: file kết quả, meta, exit code, không in câu trả lời."""
import json

from scripts import run_eval

SECRET_ANSWER = "câu-trả-lời-không-được-in-ra-màn-hình"


def perfect(case):
    """Agent giả trả đúng y golden."""
    out = {"answer": SECRET_ANSWER, "route": case["route"], "sources": list(case["sources"]), "steps": 3}
    if case["order_lookup"] != "absent":
        out["order_lookup"] = case["order_lookup"]
    return out


def targets(call, meta=None):
    return {"local": lambda: (call, meta or {"model": "fake-model", "as_of_date": run_eval.AS_OF_DATE})}


def run(monkeypatch, tmp_path, capsys, call, *argv):
    monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)
    code = run_eval.main(list(argv), targets(call))
    return code, capsys.readouterr().out, sorted(tmp_path.glob("*-local.jsonl"))


def test_dung_het_luu_file_meta(monkeypatch, tmp_path, capsys):
    code, out, files = run(monkeypatch, tmp_path, capsys, perfect)
    assert code == 0 and len(files) == 1
    lines = [json.loads(x) for x in files[0].read_text(encoding="utf-8").splitlines()]
    meta, rows = lines[0]["meta"], lines[1:]
    assert meta["target"] == "local" and meta["model"] == "fake-model" and meta["as_of_date"] == "2026-11-08"
    assert meta["cases"] == len(rows) == len(run_eval.load(run_eval.GOLDEN))
    assert meta["summary"]["TỔNG"]["ok"] == [len(rows), len(rows)]
    assert all(r["out"]["answer"] == SECRET_ANSWER and r["reference"] for r in rows)   # Day 20 cần
    assert SECRET_ANSWER not in out and "Routing accuracy" in out


def test_routing_thap_exit_1(monkeypatch, tmp_path, capsys):
    code, out, _ = run(monkeypatch, tmp_path, capsys, lambda c: {**perfect(c), "route": ["policy"]})
    assert code == 1 and "⛔" in out


def test_loi_mot_ca_khong_dung_ca_luot(monkeypatch, tmp_path, capsys):
    def flaky(case):
        if case["id"] == "m01":
            raise TimeoutError("chậm")
        return perfect(case)

    code, _, files = run(monkeypatch, tmp_path, capsys, flaky, "--only", "m01,p01")
    rows = [json.loads(x) for x in files[0].read_text(encoding="utf-8").splitlines()[1:]]
    assert [r["id"] for r in rows] == ["p01", "m01"]                 # thứ tự theo golden
    assert rows[1]["out"] == {"error": "exception:TimeoutError"} and not rows[1]["score"]["ok"]
    assert rows[0]["score"]["ok"] and code == 1                       # routing 1/2 = 50% < 85%


def test_only_id_la_bi_tu_choi(monkeypatch, tmp_path, capsys):
    import pytest
    with pytest.raises(SystemExit):
        run(monkeypatch, tmp_path, capsys, perfect, "--only", "zz99")
