# support-agent

[![test](https://github.com/thuandaohong/support-agent/actions/workflows/test.yml/badge.svg)](https://github.com/thuandaohong/support-agent/actions/workflows/test.yml)

Trợ lý chăm sóc khách hàng **multi-agent** trên AWS: trả lời câu hỏi cần ghép **hai nguồn khác loại** —
chính sách công ty (tài liệu, RAG) và dữ liệu đơn hàng (database).

Ví dụ: *"Đơn #1003 có đổi trả được không?"* → tra hạn đổi trả của gói Premium (14 ngày, tài liệu)
+ tra đơn #1003 (Premium, đã giao, đặt 6 ngày trước, database) → suy luận: **được**.

## Kiến trúc

Sơ đồ kiến trúc (mục tiêu Phase D + hiện trạng): [docs/architecture.svg](docs/architecture.svg)

Đã chạy ở local (hết Phase C):

```
ask(question, customer_id)              ← cửa vào duy nhất (agents/graph.py)
  └─ graph: START → supervisor → [policy ∥ order | (bỏ qua)] → writer → END
       • supervisor : LLM định tuyến (policy / order / cả hai / không cần) + regex mã đơn
       • policy     : search_policy → Bedrock Knowledge Base
       • order      : get_order → DynamoDB (chặn đơn người khác) + rules.py tính đổi trả/bảo hành
       • writer     : LLM diễn đạt; câu cố định khi không có dữ liệu (chào hỏi, thiếu mã đơn)
       • an toàn    : recursion_limit (bắt lỗi → câu "hệ thống bận") + steps reducer
  └─ test: unit (AWS giả, chạy trên CI) + integration (AWS thật, RUN_INTEGRATION=1)
```

`ask()` trả **hợp đồng công khai** `{answer, sources, route, order_lookup, steps, error?}` — không
trả `order_data` / `policy_hits` (dữ liệu nội bộ). Debug cần nguyên State thì dùng `run_graph()`.

Dự kiến (Phase D+):

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
| `docs/` | Sơ đồ graph, ghi chú |

## Cài đặt

```bash
# Python >= 3.10 — macOS: python3 hệ thống là 3.9, dùng bản Homebrew (đã chạy với 3.14)
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # = requirements.txt (đã pin) + pytest, ruff
cp .env.example .env   # điền POLICY_KB_ID
```

## Chạy thử

```bash
python tools/search_policy.py "Gói Premium đổi trả bao nhiêu ngày?"
python tools/get_order.py 1003 C003          # customer_id bắt buộc: đơn người khác → không thấy
python -m agents.graph "Đơn #1003 còn đổi trả được không?" --customer C003 -v   # chạy cả graph
python -m agents.try_graph                   # 18 tình huống biên (eval/graph_cases.jsonl)
python -m agents.try_supervisor              # routing accuracy trên eval/routing_cases.jsonl
```

## Container (AgentCore Runtime)

`serve.py` bọc `ask()` theo hợp đồng Runtime: `GET /ping` → `{"status":"Healthy"}`,
`POST /invocations` `{"question", "customer_id"}` → hợp đồng công khai của `ask()`. Cổng 8080, **ARM64**.

```bash
# build — Runtime BẮT BUỘC arm64; --provenance/--sbom=false → 1 manifest (ECR scan + lifecycle chạy đúng)
docker build --platform linux/arm64 --provenance=false --sbom=false -t support-agent:dev .

# chạy thử: config từ .env, credentials TẠM (không mount ~/.aws)
docker run --rm -p 8080:8080 --env-file .env \
  --env-file <(aws configure export-credentials --format env-no-export) support-agent:dev
curl localhost:8080/ping
curl -X POST localhost:8080/invocations -H 'Content-Type: application/json' \
  -d '{"question":"Đơn #1003 còn đổi trả được không?","customer_id":"C003"}'

# đẩy lên ECR — tag = git SHA (repo để tag IMMUTABLE: không ghi đè được)
REG=<account>.dkr.ecr.us-east-1.amazonaws.com
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $REG
docker tag support-agent:dev $REG/support-agent:$(git rev-parse --short HEAD)
docker push $REG/support-agent:$(git rev-parse --short HEAD)
```

`customer_id` trong payload an toàn vì Runtime dùng xác thực IAM: chỉ backend (đã kiểm JWT của
khách) gọi được, không mở cho trình duyệt. `as_of_date` không nhận từ payload (sửa được kết quả đổi trả).

ECR repo `support-agent` tạo bằng CLI (Day 58): scan on push, tag IMMUTABLE, AES256, lifecycle
(xoá image không tag sau 1 ngày, giữ 10 image gần nhất). **Cần `terraform import`** khi Terraform hoá
(cùng với bảng DynamoDB `support-orders`).

## Chạy trên AgentCore Runtime (Day 59)

Role + Runtime tạo bằng script trong [infra/runtime/](infra/runtime/README.md) (biến thật trong
`infra/runtime/runtime.env`, không commit).

```bash
./infra/runtime/03-invoke.sh "Đơn #1003 còn đổi trả được không?" C003   # 1 câu qua cloud
python scripts/invoke_runtime.py --cases                                 # 18 ca eval qua cloud
./infra/runtime/04-logs.sh 15m                                           # log CloudWatch
```

## Test (kim tự tháp)

| Tầng | Lệnh | Gọi AWS? | Khi nào chạy |
|---|---|---|---|
| Unit — logic thuần + graph với AWS giả | `python -m pytest -q` | Không | Mỗi lần sửa code; **CI** chạy mỗi push/PR (`.github/workflows/test.yml`) |
| Integration — KB, DynamoDB, cả graph thật | `RUN_INTEGRATION=1 python -m pytest -v tests/test_integration.py` | Có (~$0.005) | Trước khi merge thay đổi tool / prompt / version |
| Eval — 18 tình huống, in câu trả lời để đọc | `python -m agents.try_graph` | Có (~$0.01) | Khi đổi prompt/model (Phase E: chấm tự động) |

Test integration chỉ kiểm phần tất định (nguồn, route, order_lookup, steps), không so nguyên văn câu
trả lời của LLM. CI không cần credentials AWS nào.

| Đo | Kết quả | Ngày |
|---|---|---|
| Routing accuracy (Nova Lite, 16 câu) | 15/16 = 94% — sai `r16` (nhắc "đặt hàng" → route thừa `order`) | 2026-11-11 |
| Graph end-to-end (14 tình huống, chạy 2 lần) | route + order_lookup 14/14; kết luận đổi trả/bảo hành 14/14 cả 2 lần | 2026-11-11 |
| Graph end-to-end (18 tình huống, thêm chào hỏi / thiếu mã) | route + order_lookup 18/18 | 2026-11-14 |
| Test | 69 unit pass (0.4 s) · 5 integration pass (7 s) | 2026-11-14 |
| Container | image arm64 362 MB (bỏ `langchain-aws` không dùng: 456 → 362); `/ping` + 4 ca `/invocations` đúng trong container; ECR scan HIGH 4 → 2 (glibc chưa có bản vá) | 2026-11-15 |
| AgentCore Runtime (image `2fe1122`) | 18/18 route + order_lookup qua endpoint cloud; 0.6–1.9 s/câu khi ấm, lần đầu ~15 s (cold start); log không có nội dung câu hỏi | 2026-11-15 |

Sơ đồ graph: [docs/graph.md](docs/graph.md).

**Quy ước ngày:** agent tính hạn đổi trả theo `AS_OF_DATE` (eval: `2026-11-08`), không theo ngày hệ thống.
