"""Test lớp HTTP (serve.py) — ask() thay bằng hàm giả, không gọi AWS, chạy trên CI."""
import pytest
from fastapi.testclient import TestClient

import serve

client = TestClient(serve.app)


@pytest.fixture
def fake_ask(monkeypatch):
    calls = []

    def fake(question, customer_id, as_of_date=None):
        calls.append((question, customer_id, as_of_date))
        return {"answer": "ok", "sources": [], "route": [], "steps": 2}

    monkeypatch.setattr(serve, "ask", fake)
    return calls


def test_ping_follows_runtime_contract():
    r = client.get("/ping")
    assert r.status_code == 200 and r.json() == {"status": "Healthy"}


def test_invocation_returns_public_contract(fake_ask):
    r = client.post("/invocations", json={"question": "  Xin chào  ", "customer_id": "C003"})
    assert r.status_code == 200
    assert r.json() == {"answer": "ok", "sources": [], "route": [], "steps": 2}
    assert fake_ask == [("Xin chào", "C003", None)]   # đã strip; as_of_date không đến từ payload


@pytest.mark.parametrize("payload", [
    {"customer_id": "C003"},                                      # thiếu question
    {"question": "   ", "customer_id": "C003"},                   # chỉ khoảng trắng
    {"question": "x" * 2001, "customer_id": "C003"},              # quá dài (chặn đốt token)
    {"question": "Đơn #1003?"},                                   # thiếu customer_id
    {"question": "Đơn #1003?", "customer_id": "admin"},           # sai định dạng
    {"question": "Đơn #1003?", "customer_id": "C003", "as_of_date": "2026-11-01"},  # trường lạ
])
def test_invalid_payload_rejected_before_graph(fake_ask, payload):
    assert client.post("/invocations", json=payload).status_code == 422
    assert fake_ask == []   # không chạm tới graph → không tốn token


def test_internal_error_does_not_leak_details(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("arn:aws:dynamodb:us-east-1:123:table/support-orders AccessDenied")

    monkeypatch.setattr(serve, "ask", boom)
    r = client.post("/invocations", json={"question": "Đơn #1003?", "customer_id": "C003"})
    assert r.status_code == 500
    assert r.json() == {"error": "internal_error"} and "arn:" not in r.text


def test_api_docs_are_disabled():
    assert client.get("/docs").status_code == 404 and client.get("/openapi.json").status_code == 404
