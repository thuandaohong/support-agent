# support-agent

Trợ lý chăm sóc khách hàng **multi-agent** trên AWS: trả lời câu hỏi cần ghép **hai nguồn khác loại** —
chính sách công ty (tài liệu, RAG) và dữ liệu đơn hàng (database).

Ví dụ: *"Đơn #1003 có đổi trả được không?"* → tra hạn đổi trả của gói Premium (14 ngày, tài liệu)
+ tra đơn #1003 (Premium, đã giao, đặt 6 ngày trước, database) → suy luận: **được**.

## Kiến trúc (dự kiến)

- **LangGraph**: Supervisor điều phối → Policy agent (Bedrock Knowledge Base) · Order agent (DynamoDB) · Writer agent
- **Amazon Bedrock AgentCore**: Runtime, Memory, Identity, Observability, Gateway (tool qua MCP)
- Guardrails · Eval · CloudWatch · Terraform · GitHub Actions

## Cấu trúc

| Thư mục | Nội dung |
|---|---|
| `agents/` | Code LangGraph (supervisor + agent chuyên môn) |
| `tools/` | `search_policy`, `get_order` |
| `eval/` | Golden set + eval harness |
| `infra/` | Terraform |
| `sample-data/` | Dữ liệu synthetic — xem [sample-data/README.md](sample-data/README.md) |
| `docs/` | Sơ đồ, ghi chú |

## Cài đặt

```bash
# Python >= 3.10 — macOS: python3 hệ thống là 3.9, dùng bản Homebrew (đã chạy với 3.14)
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # điền POLICY_KB_ID
```

## Chạy thử

```bash
python tools/search_policy.py "Gói Premium đổi trả bao nhiêu ngày?"
python tools/get_order.py 1003 C003          # customer_id bắt buộc: đơn người khác → không thấy
python -m agents.try_supervisor              # routing accuracy trên eval/routing_cases.jsonl
python -m pytest -q tests                    # test không gọi AWS
```

| Đo | Kết quả | Ngày |
|---|---|---|
| Routing accuracy (Nova Lite, 16 câu) | 15/16 = 94% — sai `r16` (nhắc "đặt hàng" → route thừa `order`) | 2026-11-11 |

**Quy ước ngày:** agent tính hạn đổi trả theo `AS_OF_DATE` (eval: `2026-11-08`), không theo ngày hệ thống.
