"""scripts/tf_plan_summary.py (Day 65) — tóm tắt plan không lộ id, chặn plan có xoá / tạo lại."""
import io
import json

import pytest

from scripts import tf_plan_summary as s

SECRET = "us-east-1_SECRETPOOL"


def rc(address, actions, before=None, after=None, importing=None, mode="managed", unknown=None):
    change = {"actions": actions, "before": before, "after": after, "after_unknown": unknown or {}}
    if importing:
        change["importing"] = {"id": importing}
    return {"address": address, "mode": mode, "change": change}


def run(monkeypatch, capsys, plan, allow=False):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(plan)))
    if allow:
        monkeypatch.setenv("ALLOW_DESTROY", "1")
    code = s.main()
    return code, capsys.readouterr().out


def test_import_khong_in_id(monkeypatch, capsys):
    plan = {"resource_changes": [rc("module.auth.aws_cognito_user_pool.this", ["no-op"],
                                    before={"id": SECRET}, after={"id": SECRET}, importing=SECRET)]}
    code, out = run(monkeypatch, capsys, plan)
    assert code == 0
    assert "1 import" in out and SECRET not in out


def test_update_chi_in_ten_thuoc_tinh(monkeypatch, capsys):
    plan = {"resource_changes": [rc("module.x.aws_lambda_function.this", ["update"],
                                    before={"source_code_hash": "old", "role": SECRET, "last_modified": "t"},
                                    after={"source_code_hash": "new", "role": SECRET},
                                    unknown={"last_modified": True}, importing="support-x")]}
    code, out = run(monkeypatch, capsys, plan)
    assert code == 0
    assert "source_code_hash" in out and "last_modified" not in out
    assert "old" not in out and "new" not in out and SECRET not in out


def test_tags_all_hien_thanh_tags(monkeypatch, capsys):
    plan = {"resource_changes": [rc("module.data.aws_s3_bucket.policies", ["update"],
                                    before={"tags_all": {}}, after={"tags_all": {"project": "support-agent"}})]}
    _, out = run(monkeypatch, capsys, plan)
    assert "| tags |" in out


@pytest.mark.parametrize("actions", [["delete"], ["delete", "create"], ["create", "delete"]])
def test_xoa_hoac_tao_lai_bi_chan(monkeypatch, capsys, actions):
    plan = {"resource_changes": [rc("module.data.aws_dynamodb_table.orders", actions, before={}, after={})]}
    code, out = run(monkeypatch, capsys, plan)
    assert code == 1 and "⛔" in out


def test_allow_destroy_cho_qua(monkeypatch, capsys):
    plan = {"resource_changes": [rc("aws_x.y", ["delete"], before={}, after=None)]}
    code, _ = run(monkeypatch, capsys, plan, allow=True)
    assert code == 0


def test_bo_qua_data_source_va_no_op(monkeypatch, capsys):
    plan = {"resource_changes": [rc("data.aws_caller_identity.current", ["read"], mode="data"),
                                 rc("aws_x.y", ["no-op"], before={}, after={})]}
    code, out = run(monkeypatch, capsys, plan)
    assert code == 0 and "No changes" in out
