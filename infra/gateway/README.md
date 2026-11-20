# infra/gateway — tool get_order + search_policy qua AgentCore Gateway (Day 60–61; Terraform từ Day 65)

> **Day 65:** resource do Terraform quản ([infra/terraform/modules/gateway](../terraform/README.md)) — đổi gì thì sửa `.tf` / `terraform.tfvars` → PR → plan → merge → Approve. Script tạo / `99-destroy.sh` đã xoá; ở đây chỉ còn script vận hành / test.

Đưa hai tool ra khỏi container agent: agent gọi **AgentCore Gateway** (MCP server do AWS quản lý)
→ Gateway gọi Lambda theo tên tool:

| Tool agent thấy | Target | Lambda | Đọc gì |
|---|---|---|---|
| `orders___get_order` | `orders` | `support-get-order` | DynamoDB `support-orders` (GetItem) |
| `policies___search_policy` | `policies` | `support-search-policy` | Knowledge Base `support-policy-kb` (Retrieve) |

Role Runtime không còn quyền đọc dữ liệu nào: chỉ `InvokeModel` + "nhờ Gateway" (`InvokeGateway`).

Gateway, 2 target, 2 Lambda và 3 role: `infra/terraform/modules/gateway` + `modules/lambda_function`
(nối trong `live/main.tf`). `gateway.env` (không commit) chỉ chứa **tên** cho script test và
`infra/iam-audit.sh`; id / URL / account id không ghi ở đâu cả.

## Cách dùng

```bash
cd support-agent
cp infra/gateway/gateway.env.example infra/gateway/gateway.env   # giá trị mẫu dùng được luôn
./infra/gateway/02-test-lambda.sh          # gọi Lambda get_order trực tiếp, đóng vai Gateway (3 ca)
./infra/gateway/06-test-policy-lambda.sh   # gọi Lambda search_policy trực tiếp, đóng vai Gateway (3 ca)
python scripts/mcp_call.py                 # tools/list + ca chuẩn của 2 tool + ca input sai, qua Gateway thật
```

| File | Việc |
|---|---|
| `gateway.env.example` | Danh sách biến (mẫu, commit). Bản thật `gateway.env` không commit |
| `_env.sh` | Nạp + kiểm biến, `ACCOUNT_ID`, thư mục tạm (tự xoá), `lambda_tool_context` (dùng chung với `iam-audit.sh`) |
| `get_order.tool.json`, `search_policy.tool.json` | Tool schema (MCP `inputSchema`) — một nguồn duy nhất: Terraform đọc để tạo target, test so với `handler.REQUIRED` |
| `02-test-lambda.sh`, `06-test-policy-lambda.sh` | Gọi thẳng Lambda với `ClientContext` giống Gateway gửi |

## Các lớp quyền trên đường gọi tool

| Chặng | Ai ký | Quyền cần | Ở đâu |
|---|---|---|---|
| Runtime → Gateway | role `support-agent-runtime` (SigV4, service `bedrock-agentcore`) | `bedrock-agentcore:InvokeGateway` trên đúng 1 gateway | `modules/runtime` (`AppGatewayInvoke`) |
| Gateway → Lambda | role `support-gateway` (target `GATEWAY_IAM_ROLE`) | `lambda:InvokeFunction` trên đúng 2 function | `modules/gateway` (`InvokeToolLambdasOnly`) |
| Lambda get_order → DynamoDB | role `support-get-order-lambda` | `dynamodb:GetItem` trên đúng 1 bảng | `live/main.tf` → `module.lambda_get_order` |
| Lambda search_policy → KB | role `support-search-policy-lambda` | `bedrock:Retrieve` trên đúng 1 KB | `live/main.tf` → `module.lambda_search_policy` |

Cùng account → Lambda **không cần** resource policy (role của Gateway có quyền là đủ). Lambda không
có Function URL: chỉ gọi được qua API Invoke có IAM.

## Gateway hành xử thế nào (đo khi gọi thật, Day 60–61)

- `tools/list`, `tools/call` chạy **không cần `initialize`**, không có `Mcp-Session-Id` → mỗi request độc lập.
- Response là JSON thường (không SSE). Không ký SigV4 → HTTP 401 (JSON-RPC `-32001`).
- Tên tool = `<target>___<tool>` (`orders___get_order`). Gateway định tuyến theo tên này; Lambda nhận
  tên đầy đủ trong `context.client_context.custom["bedrockAgentCoreToolName"]` và tự cắt tiền tố.
- Gateway **tự kiểm `inputSchema`**: thiếu trường bắt buộc hoặc sai kiểu (`top_k: "3"`) → `isError: true`,
  Lambda không bị gọi. Tool không tồn tại → JSON-RPC `-32602`.
- Tool schema của Gateway **chỉ nhận** `type`, `properties`, `required`, `items`, `description`.
  `maxLength` / `minimum` / `maximum` bị từ chối lúc tạo target → giới hạn độ dài / khoảng giá trị
  ghi bằng chữ trong `description` và **Lambda tự kiểm** (`tool_invalid_input`).
- Response 2.5 KB (3 đoạn chính sách) vẫn JSON thường, không bị cắt.
- Lambda trả `{"error": ...}` thì Gateway vẫn báo `isError: false` → client phải tự đọc nội dung.
- Lambda get_order warm 6–34 ms, cold init ~0.4–0.5 s. Lambda search_policy ~0.4 s (gần hết là
  KB `retrieve`), cold init ~0.3 s. Log search_policy chỉ có `query_len`, không có nội dung câu hỏi.

## Lưu ý vận hành

- Gateway hỏng (mạng, quyền, Lambda / KB lỗi) → `order_lookup` / `policy_lookup` = `"error"`, câu cố
  định "hệ thống tra cứu … đang bận", `error` = `order_unavailable` / `policy_unavailable` /
  `tools_unavailable` — **không bao giờ** nói "không tìm thấy đơn" hay "không có thông tin".
- `policy_node` và `order_node` gọi Gateway **song song** → `mcp_client` giữ tối đa 4 kết nối/host
  (mặc định urllib3 là 1 → mất keep-alive, đo được Day 61).
- Đổi schema tool: sửa `get_order.tool.json` + `lambdas/get_order/handler.py` → PR (Terraform zip lại
  Lambda + cập nhật target trong cùng một apply).
