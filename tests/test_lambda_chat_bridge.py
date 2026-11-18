"""Bridge Lambda (Day 64) — Runtime thay bằng client giả, event giống HTTP API payload 2.0.

Không gọi AWS, chạy trên CI. Quan trọng nhất: customer_id CHỈ đến từ claims, và session băm theo khách.
"""
import io
import json

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError

from lambdas.chat_bridge import handler

TAB = "a1b2c3d4-0000-4000-8000-000000000001"
AGENT_OUT = {"answer": "Đơn #1003 còn đổi trả được.", "sources": ["01-return-policy.md", "orders/1003"],
             "route": ["policy", "order"], "order_lookup": "found", "steps": 4}


class FakeRuntime:
    def __init__(self, out=AGENT_OUT, error=None):
        self.calls, self.out, self.error = [], out, error

    def invoke_agent_runtime(self, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        return {"response": io.BytesIO(json.dumps(self.out).encode())}


@pytest.fixture
def runtime(monkeypatch):
    fake = FakeRuntime()
    monkeypatch.setattr(handler, "_client", fake)
    return fake


def event(body=None, username="c003", token_use="access", claims=True):
    ev = {"body": json.dumps(body if body is not None else {"question": "Đơn #1003 còn đổi trả được không?",
                                                             "session_id": TAB})}
    if claims:
        ev["requestContext"] = {"authorizer": {"jwt": {"claims": {
            "username": username, "token_use": token_use, "client_id": "web", "scope": "aws.cognito.signin.user.admin"}}}}
    return ev


def call(ev):
    r = handler.lambda_handler(ev, None)
    return r["statusCode"], json.loads(r["body"])


# ─── đường đúng ───

def test_customer_id_comes_from_claims_and_payload_matches_serve_contract(runtime):
    assert call(event())[0] == 200
    sent = runtime.calls[0]
    assert json.loads(sent["payload"]) == {"question": "Đơn #1003 còn đổi trả được không?", "customer_id": "C003"}
    assert sent["qualifier"] == "DEFAULT" and sent["agentRuntimeArn"] == handler.RUNTIME_ARN


def test_only_public_fields_are_returned(runtime):
    _, body = call(event())
    assert set(body) == {"answer", "sources", "route"}   # order_lookup / steps là nội bộ


def test_runtime_session_is_long_enough_and_stable_per_customer_and_tab(runtime):
    call(event()); call(event())
    s1, s2 = runtime.calls[0]["runtimeSessionId"], runtime.calls[1]["runtimeSessionId"]
    assert s1 == s2 and len(s1) >= 33 and TAB not in s1   # cùng khách + cùng tab → cùng microVM (nhớ hội thoại)


def test_other_customer_reusing_the_same_tab_id_gets_another_session(runtime):
    call(event(username="c003")); call(event(username="c020"))
    assert runtime.calls[0]["runtimeSessionId"] != runtime.calls[1]["runtimeSessionId"]


def test_base64_body_is_accepted(runtime):
    import base64
    ev = event()
    ev["body"], ev["isBase64Encoded"] = base64.b64encode(ev["body"].encode()).decode(), True
    assert call(ev)[0] == 200


# ─── danh tính: chỉ từ claims ───

@pytest.mark.parametrize("kw, reason", [
    ({"claims": False}, "no_claims"),
    ({"token_use": "id"}, "not_access_token"),
    ({"username": "admin"}, "bad_customer_id"),
    ({"username": ""}, "bad_customer_id"),
])
def test_bad_identity_is_403_and_runtime_not_called(runtime, kw, reason):
    assert call(event(**kw)) == (403, {"error": reason})
    assert runtime.calls == []


def test_customer_id_in_body_is_rejected_not_used(runtime):
    status, body = call(event({"question": "Đơn #1003?", "session_id": TAB, "customer_id": "C020"}))
    assert (status, body) == (400, {"error": "unexpected_field"}) and runtime.calls == []


# ─── body ───

@pytest.mark.parametrize("raw, reason", [
    ("not json", "invalid_json"),
    ('["a list"]', "invalid_json"),
    (json.dumps({"session_id": TAB}), "invalid_question"),
    (json.dumps({"question": "   ", "session_id": TAB}), "invalid_question"),
    (json.dumps({"question": "x" * 2001, "session_id": TAB}), "invalid_question"),
    (json.dumps({"question": "hi"}), "invalid_session_id"),
    (json.dumps({"question": "hi", "session_id": "web-default"}), "invalid_session_id"),
    ("x" * 9000, "body_too_large"),
])
def test_bad_body_is_400_and_runtime_not_called(runtime, raw, reason):
    ev = event()
    ev["body"] = raw
    assert call(ev) == (400, {"error": reason}) and runtime.calls == []


# ─── Runtime hỏng ───

@pytest.mark.parametrize("error, out", [
    (ClientError({"Error": {"Code": "AccessDeniedException", "Message": "arn:aws:..."}}, "InvokeAgentRuntime"), None),
    (ReadTimeoutError(endpoint_url="https://x"), None),
    (None, {"error": "internal_error"}),                 # container trả lỗi (serve.py 500)
])
def test_runtime_failure_is_502_without_details(monkeypatch, error, out):
    monkeypatch.setattr(handler, "_client", FakeRuntime(out=out or AGENT_OUT, error=error))
    assert call(event()) == (502, {"error": "agent_unavailable"})


def test_log_has_no_question_answer_or_customer(runtime, caplog):
    caplog.set_level("INFO")
    call(event())
    call(event(username="admin"))
    text = caplog.text
    assert "chat ok" in text and "reason=bad_customer_id" in text
    assert "1003" not in text and "C003" not in text and "c003" not in text and "đổi trả" not in text
